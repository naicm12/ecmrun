from flask import Flask, render_template, redirect, request, make_response, jsonify, flash, session
from flask_mail import Mail, Message
from flask_mysqldb import MySQL
from dotenv import load_dotenv
from datetime import datetime
from pytz import timezone
import mercadopago
import hashlib
import pdfkit
import os
import re
import random
import json
import uuid
import logging

load_dotenv()  # Carrega as variáveis do arquivo .env

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)

sdk = mercadopago.SDK(os.getenv('MP_ACCESS_TOKEN2'))

app.secret_key = os.getenv('SECRET_KEY')

# Configuração do Flask-Mail
app.config['MAIL_SERVER'] = os.getenv('SMTP_SERVER')  # Substitua pelo seu servidor SMTP
app.config['MAIL_PORT'] = os.getenv('SMTP_PORT') 
app.config['MAIL_USERNAME'] = os.getenv('EMAIL_USER') 
app.config['MAIL_PASSWORD'] = os.getenv('EMAIL_PASSWORD') 
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_MAX_EMAILS'] = None
app.config['MAIL_TIMEOUT'] = 10  # segundos
app.config['MP_ACCESS_TOKEN'] = os.getenv('MP_ACCESS_TOKEN')

mail = Mail(app)

# Configuração MySQL
app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST')
app.config['MYSQL_USER'] = os.getenv('MYSQL_USER')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD')
app.config['MYSQL_DB'] = os.getenv('MYSQL_DB')

mysql = MySQL(app)

#sdk = mercadopago.SDK(os.getenv('MP_ACCESS_TOKEN2'))

# Global variables for the receipt
receipt_data = {
    'titulo': 'Comprovante de Inscrição',
    'data': '14/01/2025',
    'evento': '4º DESAFIO 200K PORTO VELHO-HUMAITÁ - 2025',
    'endereco': 'AV. Jorge Teixeira, Espaço Alternativo - Porto Velho/RO',
    'dataevento': '04, 05 e 06/07/2025',
    'participante': 'ELIENAI CARVALHO MOMTEIRO',
    'km': 'Solo - 200 km',
    'valor': 'R$ 500,00',
    'inscricao': '123455456456',    
    'obs': 'Observações importantes sobre o evento vão aqui.'
}

var_camiseta = ""
var_apoio = ""
var_equipe = ""
var_integrantes = ""
var_email = ""

def fn_camiseta(valor):
    global var_camiseta
    var_camiseta = valor

def fn_apoio(valor):
    global var_apoio
    var_apoio = valor

def fn_equipe(valor):
    global var_equipe
    var_equipe = valor

def fn_integrantes(valor):
    global var_integrantes
    var_integrantes = valor

def fn_email(valor):
    global var_email
    var_email = valor

@app.route("/")
def index():
    return render_template("index.html")

#@app.route("/teste")
#def teste():
#    return render_template('organizer_email.html', **receipt_data)



def get_receipt_data(payment_id):
    """Função separada para buscar dados do comprovante"""
    try:
        cur = mysql.connection.cursor()
        cur.execute('''
            SELECT I.DTPAGAMENTO, E.DESCRICAO, E.LOCAL, 
                CONCAT(E.DTINICIO,' ',E.HRINICIO,' - ',E.DTFIM) as DTEVENTO,
                CONCAT(A.NOME,' ',A.SOBRENOME) as NOME_COMPLETO, 
                CONCAT(M.DISTANCIA,' / ',M.DESCRICAO) AS DISTANCIA,
                I.VALOR, I.VALOR_PGTO, I.FORMAPGTO, I.IDPAGAMENTO
            FROM ecmrun.INSCRICAO_TT I
            JOIN ecmrun.ATLETA_TT A ON A.IDATLETA = I.IDATLETA
            JOIN ecmrun.EVENTO E ON E.IDEVENTO = I.IDEVENTO
            JOIN ecmrun.EVENTO_MODALIDADE M ON M.IDITEM = I.IDITEM
            WHERE I.IDPAGAMENTO = %s
        ''', (payment_id,))
        
        data = cur.fetchone()
        cur.close()
        return data
    except Exception as e:
        app.logger.error(f"Erro ao buscar dados: {str(e)}")
        raise

#########################

#############################    

def send_organizer_notification(receipt_data):
    try:
        msg = Message(
            f'Nova Inscrição - 4º Desafio 200k - ID {receipt_data["inscricao"]}',
            sender=('ECM Run', 'adm@ecmrun.com.br'),
            recipients=['ecmsistemasdeveloper@gmail.com']
        )
        
        # Render the organizer notification template with receipt data
        msg.html = render_template('organizer_email.html', **receipt_data)
        mail.send(msg)
        app.logger.info("Notificação enviada para o organizador")
        return True
        
    except Exception as e:
        app.logger.error(f"Erro ao enviar notificação para o organizador: {str(e)}")
        return False


@app.route('/comprovante/<int:payment_id>')
def comprovante(payment_id):
    try:
        
        app.logger.info(f"Payment ID: {payment_id}")
        
        cur = mysql.connection.cursor()
        # Execute a SQL com o payment_id
        cur.execute('''
            SELECT I.DTPAGAMENTO, E.DESCRICAO, E.LOCAL, 
                CONCAT(E.DTINICIO,' ',E.HRINICIO,' - ',E.DTFIM) as DTEVENTO,
                CONCAT(A.NOME,' ',A.SOBRENOME) as NOME_COMPLETO, 
                CONCAT(M.DISTANCIA,' / ',M.DESCRICAO) AS DISTANCIA,
                I.VALOR, I.VALOR_PGTO, I.FORMAPGTO, I.IDPAGAMENTO, I.FLMAIL, I.IDINSCRICAO
            FROM ecmrun.INSCRICAO_TT I, ecmrun.ATLETA_TT A, 
            ecmrun.EVENTO E, ecmrun.EVENTO_MODALIDADE M
            WHERE M.IDITEM = I.IDITEM
            AND E.IDEVENTO = I.IDEVENTO
            AND A.IDATLETA = I.IDATLETA
            AND I.IDPAGAMENTO = %s
        ''', (payment_id,))
        
        receipt_data = cur.fetchone()
        cur.close()

        if not receipt_data:
            app.logger.info("Dados não encontrados")
            return "Dados não encontrados", 404
        
        # Converter a data de string para datetime
        #data_pagamento = datetime.strptime(receipt_data[0], '%d/%m/%Y %H:%M')  # Formato correto

        # Estruturar os dados do comprovante
        receipt_data_dict = { 
            'data': receipt_data[0],  # Formatar data
            'evento': receipt_data[1],
            'endereco': receipt_data[2],
            'dataevento': receipt_data[3],
            'participante': receipt_data[4],
            'km': receipt_data[5],
            'valor': f'R$ {receipt_data[6]:,.2f}',  # Formatar valor
            'valortotal': f'R$ {receipt_data[7]:,.2f}',  # Formatar valor
            'formapgto': receipt_data[8],
            'inscricao': str(receipt_data[9]),
            'obs': 'Sua inscrição dá direito a: Número de peito, camiseta, viseira, sacolinha, e após concluir: medalha e troféu. Obs: Será apenas um troféu por equipe.'
        }
        
        app.logger.info("Dados da Inscrição:")
        app.logger.info(receipt_data)

        flmail = receipt_data[10]
        id_inscricao = receipt_data[11]
        app.logger.info(f' FLMAIL: { flmail }')
        app.logger.info(f' ID INSC: { id_inscricao }')


        if flmail == 'N':

            # Enviar email com os dados do comprovante
            send_email(receipt_data_dict)
        
            # Enviar notificação para o organizador
            send_organizer_notification(receipt_data_dict)

            cur1 = mysql.connection.cursor()
            cur1.execute('''
                UPDATE ecmrun.INSCRICAO_TT SET FLMAIL = 'S'
                WHERE IDINSCRICAO = %s
            ''', (id_inscricao,))

            mysql.connection.commit()
            cur1.close()


        return render_template('comprovante_insc.html', **receipt_data_dict)

    except Exception as e:
        app.logger.error(f"Erro ao buscar dados do comprovante: {str(e)}")
        return "Erro ao buscar dados", 500

@app.route('/vercomprovante/<int:payment_id>')
def vercomprovante(payment_id):
    try:
        
        app.logger.info(f"Payment ID: {payment_id}")
        
        cur = mysql.connection.cursor()
        # Execute a SQL com o payment_id
        cur.execute('''
            SELECT I.DTPAGAMENTO, E.DESCRICAO, E.LOCAL, 
                CONCAT(E.DTINICIO,' ',E.HRINICIO,' - ',E.DTFIM) as DTEVENTO,
                CONCAT(A.NOME,' ',A.SOBRENOME) as NOME_COMPLETO, 
                CONCAT(M.DISTANCIA,' / ',M.DESCRICAO) AS DISTANCIA,
                I.VALOR, I.VALOR_PGTO, I.FORMAPGTO, I.IDPAGAMENTO, I.FLMAIL, I.IDINSCRICAO
            FROM ecmrun.INSCRICAO_TT I, ecmrun.ATLETA_TT A, 
            ecmrun.EVENTO E, ecmrun.EVENTO_MODALIDADE M
            WHERE M.IDITEM = I.IDITEM
            AND E.IDEVENTO = I.IDEVENTO
            AND A.IDATLETA = I.IDATLETA
            AND I.IDPAGAMENTO = %s
        ''', (payment_id,))
        
        receipt_data = cur.fetchone()
        cur.close()

        if not receipt_data:
            app.logger.info("Dados não encontrados")
            return "Dados não encontrados", 404
        
        # Converter a data de string para datetime
        #data_pagamento = datetime.strptime(receipt_data[0], '%d/%m/%Y %H:%M:%S')  # Formato correto

        flmail = receipt_data[10]
        id_inscricao = receipt_data[11]
        app.logger.info(f' FLMAIL: { flmail }')
        app.logger.info(f' ID INSC: { id_inscricao }')

        # Estruturar os dados do comprovante
        receipt_data_dict = { 
            'data': receipt_data[0],  # Formatar data
            'evento': receipt_data[1],
            'endereco': receipt_data[2],
            'dataevento': receipt_data[3],
            'participante': receipt_data[4],
            'km': receipt_data[5],
            'valor': f'R$ {receipt_data[6]:,.2f}',  # Formatar valor
            'valortotal': f'R$ {receipt_data[7]:,.2f}',  # Formatar valor
            'formapgto': receipt_data[8],
            'inscricao': str(receipt_data[9]),
            'obs': 'Sua inscrição dá direito a: Número de peito, camiseta, viseira, sacolinha, e após concluir: medalha e troféu. Obs: Será apenas um troféu por equipe.'
        }
        
        app.logger.info("Dados da Inscrição:")
        app.logger.info(receipt_data)

        return render_template('comprovante_insc.html', **receipt_data_dict)

    except Exception as e:
        app.logger.error(f"Erro ao buscar dados do comprovante: {str(e)}")
        return "Erro ao buscar dados", 500

@app.route('/comprovanteemail/<int:payment_id>')
def comprovanteemail(payment_id):
    try:
        
        app.logger.info(f"Payment ID: {payment_id}")
        
        cur = mysql.connection.cursor()
        # Execute a SQL com o payment_id
        cur.execute('''
            SELECT I.DTPAGAMENTO, E.DESCRICAO, E.LOCAL, 
                CONCAT(E.DTINICIO,' ',E.HRINICIO,' - ',E.DTFIM) as DTEVENTO,
                CONCAT(A.NOME,' ',A.SOBRENOME) as NOME_COMPLETO, 
                CONCAT(M.DISTANCIA,' / ',M.DESCRICAO) AS DISTANCIA,
                I.VALOR, I.VALOR_PGTO, I.FORMAPGTO, I.IDPAGAMENTO
            FROM ecmrun.INSCRICAO_TT I, ecmrun.ATLETA_TT A, 
            ecmrun.EVENTO E, ecmrun.EVENTO_MODALIDADE M
            WHERE M.IDITEM = I.IDITEM
            AND E.IDEVENTO = I.IDEVENTO
            AND A.IDATLETA = I.IDATLETA
            AND I.IDPAGAMENTO = %s
        ''', (payment_id,))
        
        receipt_data = cur.fetchone()
        cur.close()

        if not receipt_data:
            app.logger.info("Dados não encontrados")
            return "Dados não encontrados", 404
        
        # Estruturar os dados do comprovante
        receipt_data_dict = { 
            'data': receipt_data[0],  # Formatar data
            'evento': receipt_data[1],
            'endereco': receipt_data[2],
            'dataevento': receipt_data[3],
            'participante': receipt_data[4],
            'km': receipt_data[5],
            'valor': f'R$ {receipt_data[6]:,.2f}',  # Formatar valor
            'valortotal': f'R$ {receipt_data[7]:,.2f}',  # Formatar valor
            'formapgto': receipt_data[8],
            'inscricao': str(receipt_data[9]),
            'obs': 'Sua inscrição dá direito a: Número de peito, camiseta, viseira, sacolinha, e após concluir: medalha e troféu. Obs: Será apenas um troféu por equipe.'
        }
        
        app.logger.info("Dados da Inscrição:")
        app.logger.error(receipt_data)

        return render_template('comprovante_email.html', **receipt_data_dict)

    except Exception as e:
        app.logger.error(f"Erro ao buscar dados do comprovante: {str(e)}")
        return "Erro ao buscar dados", 500



@app.route('/pagpix')
def pagpix():
    return render_template('pagpix.html')

###############

#@app.route('/checkout')
#def checkout():
#    return render_template('checkout.html')

#@app.route('/checkout2')
#def checkout2():
#    return render_template('checkout2.html')

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    app.logger.info(f"Webhook received: {data}")
    
    if data['type'] == 'payment':
        payment_info = sdk.payment().get(data['data']['id'])
        app.logger.info(f"Payment info: {payment_info}")
    
    return jsonify({'status': 'ok'}), 200


#@app.route('/process_payment', methods=['POST'])
#def process_payment():
#    try:
#        app.logger.info("Dados recebidos:")
#        app.logger.info(request.form)
        
#        # Validar dados recebidos
#        required_fields = ['token', 'transaction_amount', 'email', 'doc_type', 'doc_number']
#        for field in required_fields:
#            if field not in request.form:
#                raise ValueError(f"Campo obrigatório ausente: {field}")

#        # Gerar referência externa única
#        external_reference = str(uuid.uuid4())
        
#        # Criar preferência de pagamento
#        preference_data = {
#            "items": [{
#                "title": request.form['description'],
#                "quantity": 1,
#                "currency_id": "BRL",
#                "unit_price": float(request.form['transaction_amount']),
#                "description": request.form['description'],
#                "category_id": "others"
#            }],
#            "notification_url": "https://ecmrun.com.br/webhook",
#            "external_reference": external_reference
#        }
        
#        # Criar preferência e obter o ID
#        preference_response = sdk.preference().create(preference_data)
#        preference_id = preference_response["response"]["id"]
        
#        payment_data = {
#            "transaction_amount": float(request.form['transaction_amount']),
#            "token": request.form['token'],
#            "description": request.form['description'],
#            "installments": int(request.form['installments']),
#            "payment_method_id": request.form['payment_method_id'],
#            "external_reference": external_reference,
#            "notification_url": "https://ecmrun.com.br/webhook",
#            "payer": {
#                "email": request.form['email'],
#                "first_name": request.form['first_name'],
#                "last_name": request.form['last_name'],
#                "identification": {
#                    "type": request.form['doc_type'],
#                    "number": request.form['doc_number']
#                }
#            }
#            # Remover >> preference_id": preference_id
#        }

#        app.logger.info("Dados do pagamento:")
#        app.logger.info(payment_data)
        
#        payment_response = sdk.payment().create(payment_data)
        
#        app.logger.info("Resposta do pagamento:")
#        app.logger.info(payment_response)
        
#        if "error" in payment_response:
#            return jsonify(payment_response), 400
            
#        return jsonify(payment_response["response"]), 200
        
#    except ValueError as e:
#        app.logger.error(f"Erro de validação: {str(e)}")
#        return jsonify({"error": str(e)}), 400
#    except Exception as e:
#        app.logger.error(f"Erro no processamento: {str(e)}")
#        return jsonify({"error": str(e)}), 400


@app.route('/process_payment', methods=['POST'])
def process_payment():
    try:
        app.logger.info("Dados recebidos:")
        payment_data = request.json
        app.logger.info(payment_data)
        
        # Validar dados recebidos
        required_fields = [
            'token', 
            'transaction_amount', 
            'installments', 
            'payment_method_id',
            'payer'
        ]
        
        for field in required_fields:
            if field not in payment_data:
                raise ValueError(f"Campo obrigatório ausente: {field}")

        # Gerar referência externa única
        external_reference = str(uuid.uuid4())
        
        # Criar preferência de pagamento
        preference_data = {
            "items": [{
                "title": payment_data.get('description', 'Produto'),
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": float(payment_data['transaction_amount']),
                "description": payment_data.get('description_item', 'Produto'),
                "category_id": "others"
            }],
            "notification_url": "https://ecmrun.com.br/webhook",
            "external_reference": external_reference
        }
        
        # Criar preferência
        preference_response = sdk.preference().create(preference_data)
        
        if "response" not in preference_response:
            raise ValueError("Erro ao criar preferência de pagamento")
            
        # Preparar dados do pagamento
        payment_info = {
            "transaction_amount": float(payment_data['transaction_amount']),
            "token": payment_data['token'],
            "description": payment_data.get('description', 'Produto'),
            "installments": int(payment_data['installments']),
            "payment_method_id": payment_data['payment_method_id'],
            "external_reference": external_reference,
            "notification_url": "https://ecmrun.com.br/webhook",
            "payer": payment_data['payer']
        }

        app.logger.info("Dados do pagamento:")
        app.logger.info(payment_info)
        
        # Processar pagamento
        payment_response = sdk.payment().create(payment_info)
        
        app.logger.info("Resposta do pagamento:")
        app.logger.info(payment_response)
        
        if "response" not in payment_response:
            return jsonify({
                "error": "Erro ao processar pagamento",
                "details": payment_response.get("message", "Erro desconhecido")
            }), 400
            
        return jsonify(payment_response["response"]), 200
        
    except ValueError as e:
        app.logger.error(f"Erro de validação: {str(e)}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        app.logger.error(f"Erro no processamento: {str(e)}")
        return jsonify({"error": str(e)}), 400

#  GUARDAR POR ESSA FOI A QEU FUNCIONOU 
#
# @app.route('/process_payment', methods=['POST'])
# def process_payment():
#     payment_data = {
#         "transaction_amount": float(request.form['transaction_amount']),
#         "token": request.form['token'],
#         "description": request.form['description'],
#         "installments": int(request.form['installments']),
#         "payment_method_id": request.form['payment_method_id'],
#         "payer": {
#             "email": request.form['email'],
#             "identification": {
#                 "type": request.form['doc_type'],
#                 "number": request.form['doc_number']
#             }
#         }
#     }

#     payment_response = sdk.payment().create(payment_data)
    
#     return jsonify(payment_response)


##########################################

@app.route('/get_evento_data')
def get_evento_data():
    try:
        cur = mysql.connection.cursor()
        cur.execute('''
            SELECT E.IDEVENTO, E.DESCRICAO, E.DTINICIO, E.DTFIM, E.HRINICIO,
                E.LOCAL, E.CIDADEUF, E.INICIO_INSCRICAO, E.FIM_INSCRICAO,
                M.IDITEM, M.DESCRICAO AS MODALIDADE, M.DISTANCIA, M.KM,
                M.VLINSCRICAO, M.VLMEIA, M.VLTAXA
            FROM ecmrun.EVENTO E, ecmrun.EVENTO_MODALIDADE M
            WHERE M.IDEVENTO = E.IDEVENTO
                AND E.IDEVENTO = 1
        ''')
        
        results = cur.fetchall()
        cur.close()
        
        if not results:
            return jsonify({'error': 'Evento não encontrado'}), 404
            
        # Estruturar os dados
        evento_data = {
            'idevento': results[0][0],
            'descricao': results[0][1],
            'dtinicio': results[0][2],
            'dtfim': results[0][3],
            'hrinicio': results[0][4],
            'local': results[0][5],
            'cidadeuf': results[0][6],
            'inicio_inscricao': results[0][7],
            'fim_inscricao': results[0][8],
            'iditem': results[0][9],
            'modalidades': results[0][10]
        }
        
        # Adicionar todas as modalidades
        for row in results:
            modalidade = {
                'iditem': row[9],
                'descricao': row[10],
                'distancia': row[11],
                'km': row[12],
                'vlinscricao': float(row[13]) if row[13] else 0,
                'vlmeia': float(row[14]) if row[14] else 0,
                'vltaxa': float(row[15]) if row[15] else 0
            }
            evento_data['modalidades'].append(modalidade)
            
        return jsonify(evento_data)
        
    except Exception as e:
        print(f"Erro ao buscar dados do evento: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/desafio200k')
def desafio200k():
    try:
        cur = mysql.connection.cursor()
        cur.execute('''
            SELECT E.IDEVENTO, E.DESCRICAO, E.DTINICIO, E.DTFIM, E.HRINICIO,
                E.LOCAL, E.CIDADEUF, E.INICIO_INSCRICAO, E.FIM_INSCRICAO,
                M.IDITEM, M.DESCRICAO AS MODALIDADE, M.DISTANCIA, M.KM,
                M.VLINSCRICAO, M.VLMEIA, M.VLTAXA
            FROM ecmrun.EVENTO E, ecmrun.EVENTO_MODALIDADE M
            WHERE M.IDEVENTO = E.IDEVENTO
                AND E.IDEVENTO = 1
        ''')
        
        results = cur.fetchall()
        cur.close()
        
        if not results:
            return render_template('desafio200k.html', titulo="Evento não encontrado", modalidades=[])
            
        evento_titulo = results[0][1]  # DESCRICAO do evento
        modalidades = [{'id': row[9], 'descricao': row[10]} for row in results]
            
        return render_template('desafio200k.html', titulo=evento_titulo, modalidades=modalidades)
        
    except Exception as e:
        print(f"Erro ao carregar página: {str(e)}")
        return render_template('desafio200k.html', titulo="Erro ao carregar evento", modalidades=[])

@app.route('/get_modalidade_valores/<int:iditem>')
def get_modalidade_valores(iditem):
    try:
        cur = mysql.connection.cursor()
        cur.execute('''
            SELECT VLINSCRICAO, VLTAXA 
            FROM ecmrun.EVENTO_MODALIDADE 
            WHERE IDITEM = %s
        ''', (iditem,))
        
        result = cur.fetchone()
        cur.close()
        
#        if not result:
#            return jsonify({'error': 'Modalidade não encontrada'}), 404
#            
#        return jsonify({
#            'vlinscricao': float(result[0]) if result[0] else 0,
#            'vltaxa': float(result[1]) if result[1] else 0
#
#        })
        

        if result:
            vlinscricao = float(result[0]) if result[0] else 0
            vltaxa = float(result[1]) if result[1] else 0

            # Store in session
            session['cat_vlinscricao'] = vlinscricao
            session['cat_vltaxa'] = vltaxa
            session['cat_iditem'] = iditem
            
            return jsonify({
                'vlinscricao': vlinscricao,
                'vltaxa': vltaxa,
                'iditem': iditem
            })

        else:
            return jsonify({
                'success': False,
                'message': 'Usuário ou senha inválidos'
            }), 401


    except Exception as e:
        print(f"Erro ao buscar valores da modalidade: {str(e)}")
        return jsonify({'error': str(e)}), 500


################


@app.route('/cadastro_atleta')
def cadastro_atleta():
    return render_template('cadastro_atleta.html')

@app.route('/autenticar', methods=['POST'])
def autenticar():
    email = request.form.get('email')
    cpf = request.form.get('cpf')
    categoria = request.form.get('categoria')

    verification_code = str(random.randint(1000, 9999))
    session['verification_code'] = verification_code
    
    return render_template('autenticar200k.html', verification_code=verification_code)

@app.route('/salvar-cadastro', methods=['POST'])
def salvar_cadastro():
    try:
        data = request.get_json()
        
        # Formatar a data de nascimento
        dia = str(data.get('dia_nasc')).zfill(2)  # Adiciona zero à esquerda se necessário
        mes = str(data.get('mes_nasc')).zfill(2)  # Converte o mês para número com dois dígitos
        ano = data.get('ano_nasc')
        data_nascimento = f"{dia}/{mes}/{ano}"
        
        # Gerar data e hora atual no formato requerido
        data_cadastro = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
        # Criptografar a senha usando SHA-256
        senha = data.get('senha')
        senha_hash = hashlib.sha256(senha.encode()).hexdigest()
        
        # Preparar query e parâmetros
        query = """
        INSERT INTO ecmrun.ATLETA_TT (
            CPF, NOME, SOBRENOME, DTNASCIMENTO, NRCELULAR, SEXO, 
            EMAIL, ID_ENDERECO, EQUIPE, TEL_EMERGENCIA, 
            CONT_EMERGENCIA, SENHA, ATIVO, DTCADASTRO
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """
        
        # Remover caracteres não numéricos do CPF e telefones
        cpf_limpo = re.sub(r'\D', '', data.get('cpf'))
        celular_limpo = re.sub(r'\D', '', data.get('celular'))
        tel_emergencia_limpo = re.sub(r'\D', '', data.get('telefone_emergencia')) if data.get('telefone_emergencia') else None
        
        params = (
            cpf_limpo,
            data.get('primeiro_nome').upper(),
            data.get('sobrenome').upper(),
            data_nascimento,
            celular_limpo,
            data.get('sexo'),
            data.get('email'),
            data.get('id_logradouro'),  # ID obtido na pesquisa do CEP
            data.get('equipe').upper() if data.get('equipe') else None,
            tel_emergencia_limpo,
            data.get('contato_emergencia').upper() if data.get('contato_emergencia') else None,
            senha_hash,
            'S',  # ATIVO
            data_cadastro
        )
        
        # Executar a query
        cur = mysql.connection.cursor()
        cur.execute(query, params)
        mysql.connection.commit()
        cur.close()
        
        return jsonify({
            'success': True,
            'message': 'Cadastro realizado com sucesso!'
        })
        
    except Exception as e:
        print(f"Erro ao salvar cadastro: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Erro ao realizar cadastro. Por favor, tente novamente.'
        }), 500


@app.route('/enviar-codigo-verificacao', methods=['POST'])
def enviar_codigo_verificacao():
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({'success': False, 'message': 'Email não fornecido'}), 400

        # Gerar código de verificação
        verification_code = str(random.randint(1000, 9999))
        
        # Armazenar na sessão
        session['verification_code'] = verification_code
        session['verification_email'] = email
        
        # Simplificar o remetente
        #sender = 'adm@ecmrun.com.br'
        sender = "ECM RUN <adm@ecmrun.com.br>"

        # Criar mensagem com configuração mais simples
        msg = Message(
            'Código de Verificação - ECM Run',
            sender=sender,
            recipients=[email]
        )

        # Template HTML do email
        msg.html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #4376ac;">Verificação de Cadastro - ECM Run</h2>
            <p>Olá,</p>
            <p>Seu código de verificação é:</p>
            <h1 style="color: #4376ac; font-size: 32px; letter-spacing: 5px;">{verification_code}</h1>
            <p>Este código é válido por 10 minutos.</p>
            <p>Se você não solicitou este código, por favor ignore este email.</p>
            <br>
            <p>Atenciosamente,<br>Equipe ECM Run</p>
        </div>
        """

        # Adicionar logs para debug
        print(f'Tentando enviar email para: {email}')
        print(f'Código de verificação: {verification_code}')
        
        # Enviar email com tratamento de erro específico
        try:
            mail.send(msg)
            print('Email enviado com sucesso')
        except Exception as mail_error:
            print(f'Erro ao enviar email: {str(mail_error)}')
            return jsonify({
                'success': False,
                'message': f'Erro ao enviar email: {str(mail_error)}'
            }), 500

        return jsonify({
            'success': True,
            'message': 'Código de verificação enviado com sucesso'
        })
        
    except Exception as e:
        print(f"Erro geral na rota: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Erro ao processar requisição: {str(e)}'
        }), 500
    

@app.route('/verificar-codigo', methods=['POST'])
def verificar_codigo():
    try:
        data = request.get_json()
        codigo_informado = data.get('codigo')
        senha = data.get('senha')
        
        codigo_correto = session.get('verification_code')
        email = session.get('verification_email')
        
        if not codigo_correto or not email:
            return jsonify({
                'success': False,
                'message': 'Sessão expirada. Por favor, solicite um novo código.'
            }), 400
        
        if codigo_informado != codigo_correto:
            return jsonify({
                'success': False,
                'message': 'Código inválido'
            }), 400
            
        # Aqui você pode adicionar o código para salvar o usuário no banco de dados
        # com a senha criptografada
        
        # Limpar dados da sessão
        session.pop('verification_code', None)
        session.pop('verification_email', None)
        
        return jsonify({
            'success': True,
            'message': 'Código verificado com sucesso'
        })
        
    except Exception as e:
        print(f"Erro ao verificar código: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Erro ao verificar código'
        }), 500


@app.route('/estados')
def estados():
    with open('static/json/estados.json', encoding='utf-8') as f:
        data = json.load(f)
    return jsonify(data)

@app.route('/municipios')
def municipios():
    with open('static/json/municipios.json', encoding='utf-8') as f:
        data = json.load(f)
    return jsonify(data)

@app.route('/inscricao200k')
def inscricao200k():
    return render_template('inscricao200k.html')

@app.route('/formulario200k')
def formulario200k():
    return render_template('formulario200k.html')

@app.route('/login')
def login():
    return render_template('login.html')

def validar_cpf(cpf):
    # Remove caracteres não numéricos
    cpf = ''.join(re.findall(r'\d', str(cpf)))
    
    # Verifica se o CPF tem 11 dígitos
    if len(cpf) != 11:
        return False
    
    # Verifica se todos os dígitos são iguais (ex: 111.111.111-11)
    if cpf == cpf[0] * 11:
        return False
    
    # Calcula o primeiro dígito verificador
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    primeiro_dv = 11 - (soma % 11)
    primeiro_dv = 0 if primeiro_dv >= 10 else primeiro_dv
    
    # Calcula o segundo dígito verificador
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    segundo_dv = 11 - (soma % 11)
    segundo_dv = 0 if segundo_dv >= 10 else segundo_dv
    
    # Verifica se os dígitos verificadores estão corretos
    return cpf[-2:] == f"{primeiro_dv}{segundo_dv}"


@app.route('/validar-cpf', methods=['GET'])
def validar_cpf_route():
    
    cpf = request.args.get('cpf', '')
    # Remove caracteres não numéricos
    cpf = ''.join(filter(str.isdigit, cpf))
    is_valid = validar_cpf(cpf)

    return jsonify({'valid': is_valid})

@app.route('/verificar-cpf', methods=['GET'])
def verificar_cpf_existente():
    cpf = request.args.get('cpf', '')
    # Remove caracteres não numéricos
    cpf = ''.join(filter(str.isdigit, cpf))
    

    try:
        cur = mysql.connection.cursor()
        cur.execute('SELECT IDATLETA FROM ecmrun.ATLETA_TT WHERE CPF = %s', (cpf,))
        result = cur.fetchone()
        cur.close()
        
        return jsonify({'exists': bool(result)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def send_email(receipt_data):
    try:
        # Recuperar o email do atleta do banco de dados
        cur = mysql.connection.cursor()
        cur.execute('''
            SELECT A.EMAIL
            FROM ecmrun.ATLETA_TT A
            JOIN ecmrun.INSCRICAO_TT I ON I.IDATLETA = A.IDATLETA
            WHERE I.IDPAGAMENTO = %s
        ''', (receipt_data['inscricao'],))
        
        email_result = cur.fetchone()
        cur.close()

        if not email_result or not email_result[0]:
            app.logger.error("Email do atleta não encontrado")
            return False

        recipient_email = email_result[0]
        
        msg = Message(
            f'Comprovante de Inscrição - ID {receipt_data["inscricao"]}',
            sender=('ECM Run', 'adm@ecmrun.com.br'),
            recipients=[recipient_email]
        )
        
        msg.html = render_template('comprovante_email.html', **receipt_data)
        mail.send(msg)
        return True
        
    except Exception as e:
        app.logger.error(f"Erro ao enviar email: {str(e)}")
        return False

# ### auterada pelo Claude
# def send_email(receipt_data):
#     # Renderiza o template HTML com os dados do recibo
#     html_content = render_template('comprovante_email.html', **receipt_data)

#     # Criação da mensagem de e-mail
#     msg = Message(subject='Desafio 200k - Comprovante Inscrição',
#                   sender='adm@ecmrun.com.br',
#                   recipients=[var_email])  # Aqui você pode pegar o email do localStorage se estiver usando JS no frontend

#     # Define o corpo do e-mail como HTML
#     msg.html = html_content

#     # Envia o e-mail
#     mail.send(msg)
#     app.logger.info(f"Enviado Email para: {var_email}")


###################

@app.route('/pesquisarCEP', methods=['GET'])
def pesquisar_cep():
    try:
        cep = request.args.get('cep', '').strip()
        
        # Remove caracteres não numéricos do CEP
        cep = ''.join(filter(str.isdigit, cep))
        
        if not cep or len(cep) != 8:
            return jsonify({'error': 'CEP inválido'}), 400
            
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT l.id_logradouro, l.CEP, upper(l.descricao) as descricao, l.UF, l.complemento, 
                   upper(l.descricao_sem_numero) as descricao_sem_numero, 
                   upper(l.descricao_cidade) as descricao_cidade,
                   upper(l.descricao_bairro) as descricao_bairro, upper(e.nome) as estado
            FROM ecmrun.logradouro l, ecmrun.estado e
            WHERE e.uf = l.UF AND l.CEP =  %s
        """, (cep,))
        
        result = cur.fetchone()
        cur.close()
        
        if result:
            return jsonify({
                'success': True,
                'data': {
                    'id_logradouro': result[0],
                    'cep': result[1],
                    'descricao': result[2],
                    'uf': result[3],
                    'complemento': result[4],
                    'descricao_sem_numero': result[5],
                    'descricao_cidade': result[6],
                    'descricao_bairro': result[7],
                    'estado': result[8]
                }
            })
        else:
            return jsonify({'success': False, 'message': 'CEP não encontrado'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/autenticar-login', methods=['POST'])
def autenticar_login():
    try:
        data = request.get_json()
        cpf_email = data.get('cpf_email')
        senha = data.get('senha')
        
        # Hash the password for comparison
        senha_hash = hashlib.sha256(senha.encode()).hexdigest()
        
        cur = mysql.connection.cursor()
        
        # Verifique se a entrada é e-mail ou CPF e consulte adequadamente
        if '@' in cpf_email:
            # Query for email
            cur.execute("""
                SELECT 
                    COALESCE(A.NOME, '') AS NOME, 
                    COALESCE(A.SOBRENOME, '') AS SOBRENOME, 
                    COALESCE(A.EMAIL, '') AS EMAIL, 
                    COALESCE(A.CPF, '') AS CPF, 
                    COALESCE(A.DTNASCIMENTO, '') AS DTNASCIMENTO, 
                    COALESCE(A.NRCELULAR, '') AS NRCELULAR, 
                    COALESCE(A.SEXO, '') AS SEXO, 
                    COALESCE(A.IDATLETA, '') AS IDATLETA, 
                    COALESCE(M.DESCRICAO, '') AS MODALIDADE, 
                    COALESCE(I.IDEVENTO, '') AS IDEVENTO, 
                    COALESCE(I.APOIO, '') AS APOIO, 
                    COALESCE(I.NOME_EQUIPE, '') AS NOME_EQUIPE,
                    COALESCE(I.INTEGRANTES, '') AS INTEGRANTES,
                    COALESCE(I.CAMISETA, '') AS CAMISETA,
                    COALESCE(I.VALOR, '') AS VALOR,
                    COALESCE(I.TAXA, '') AS TAXA,
                    COALESCE(I.VALOR_PGTO, '') AS VALOR_PGTO,
                    COALESCE(I.DTPAGAMENTO, '') AS DTPAGAMENTO,
                    COALESCE(I.FORMAPGTO, '') AS FORMAPGTO,
                    COALESCE(I.IDPAGAMENTO, '') AS IDPAGAMENTO,
                    E.DTINICIO
                FROM ecmrun.ATLETA_TT A
                JOIN ecmrun.EVENTO E ON E.IDEVENTO = 1
                LEFT JOIN ecmrun.INSCRICAO_TT I ON I.IDATLETA = A.IDATLETA AND I.IDEVENTO = E.IDEVENTO
                LEFT JOIN ecmrun.EVENTO_MODALIDADE M ON M.IDITEM = I.IDITEM
                WHERE A.EMAIL = %s AND A.SENHA = %s AND A.ATIVO = 'S'
            """, (cpf_email, senha_hash))
        else:
            # Remove non-numeric characters from CPF
            cpf = ''.join(filter(str.isdigit, cpf_email))
            cur.execute("""
                SELECT 
                    COALESCE(A.NOME, '') AS NOME, 
                    COALESCE(A.SOBRENOME, '') AS SOBRENOME, 
                    COALESCE(A.EMAIL, '') AS EMAIL, 
                    COALESCE(A.CPF, '') AS CPF, 
                    COALESCE(A.DTNASCIMENTO, '') AS DTNASCIMENTO, 
                    COALESCE(A.NRCELULAR, '') AS NRCELULAR, 
                    COALESCE(A.SEXO, '') AS SEXO, 
                    COALESCE(A.IDATLETA, '') AS IDATLETA, 
                    COALESCE(M.DESCRICAO, '') AS MODALIDADE, 
                    COALESCE(I.IDEVENTO, '') AS IDEVENTO, 
                    COALESCE(I.APOIO, '') AS APOIO, 
                    COALESCE(I.NOME_EQUIPE, '') AS NOME_EQUIPE,
                    COALESCE(I.INTEGRANTES, '') AS INTEGRANTES,
                    COALESCE(I.CAMISETA, '') AS CAMISETA,
                    COALESCE(I.VALOR, '') AS VALOR,
                    COALESCE(I.TAXA, '') AS TAXA,
                    COALESCE(I.VALOR_PGTO, '') AS VALOR_PGTO,
                    COALESCE(I.DTPAGAMENTO, '') AS DTPAGAMENTO,
                    COALESCE(I.FORMAPGTO, '') AS FORMAPGTO,
                    COALESCE(I.IDPAGAMENTO, '') AS IDPAGAMENTO,
                    E.DTINICIO
                FROM ecmrun.ATLETA_TT A
                JOIN ecmrun.EVENTO E ON E.IDEVENTO = 1
                LEFT JOIN ecmrun.INSCRICAO_TT I ON I.IDATLETA = A.IDATLETA AND I.IDEVENTO = E.IDEVENTO
                LEFT JOIN ecmrun.EVENTO_MODALIDADE M ON M.IDITEM = I.IDITEM
                WHERE A.CPF = %s AND A.SENHA = %s AND A.ATIVO = 'S'
            """, (cpf, senha_hash))
        
        result = cur.fetchone()
        cur.close()
        
        if result:
            nome_completo = f"{result[0]} {result[1]}"
            email = result[2]
            vcpf = result[3]
            dtnascimento = result[4]
            celular = result[5]
            sexo = result[6]
            idatleta = result[7]
            modalidade = result[8]
            apoio = result[10]
            equipe200 = result[11]
            integrantes = result[12]
            camiseta = result[13]
            valor = result[14]
            taxa = result[15]
            valortotal = result[16]
            dtpagamento = result[17]
            formapgto = result[18]
            idpagamento = result[19]
            dtinicio = result[20]

            # Converta as strings para objetos datetime
            dt_nascimento = datetime.strptime(dtnascimento, "%d/%m/%Y")
            dt_inicio = datetime.strptime(dtinicio, "%d/%m/%Y")

            # Calcule a idade
            idade = dt_inicio.year - dt_nascimento.year - ((dt_inicio.month, dt_inicio.day) < (dt_nascimento.month, dt_nascimento.day))
            app.logger.info(f'Idade: { idade }')
            app.logger.info(f'Data Evento: { dtinicio }')
                    
        
            # Store in session
            session['user_name'] = nome_completo
            session['user_email'] = email
            session['user_cpf'] = vcpf
            session['user_dtnascimento'] = dtnascimento
            session['user_dataevento'] = dtinicio
            session['user_idade'] = str(idade)
            session['user_celular'] = celular
            session['user_sexo'] = sexo
            session['user_idatleta'] = idatleta
            session['insc_modalidade'] = modalidade
            session['insc_apoio'] = apoio
            session['insc_equipe200'] = equipe200
            session['insc_integrantes'] = integrantes
            session['insc_camiseta'] = camiseta
            session['insc_valor'] = valor
            session['insc_taxa'] = taxa
            session['insc_valortotal'] = valortotal
            session['insc_dtpagamento'] = dtpagamento
            session['insc_formapgto'] = formapgto
            session['insc_idpagamento'] = idpagamento
        
            return jsonify({
                'success': True,
                'nome': nome_completo,
                'email': email,
                'cpf': vcpf,
                'dtnascimento': dtnascimento,
                'idade': str(idade),
                'celular': celular,
                'sexo': sexo,
                'idatleta': idatleta,
                'modalidade': modalidade,
                'apoio': apoio,
                'equipe200': equipe200,
                'integrantes': integrantes,
                'camiseta': camiseta,
                'valor': valor,
                'taxa': taxa,
                'valortotal': valortotal,
                'dtpagamento': dtpagamento,
                'formapgto': formapgto,
                'idpagamento': idpagamento,
                'dataevendo': dtinicio
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Usuário ou senha inválidos'
            }), 401
            
    except Exception as e:
        print(f"Erro na autenticação: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Erro ao realizar autenticação'
        }), 500
    

@app.route('/pagamento')
def pagamento():
    # Get values from session
    vlinscricao = session.get('cat_vlinscricao', 0)
    vltaxa = session.get('cat_vltaxa', 0)
    valor_total = float(vlinscricao) + float(vltaxa)
    
    return render_template('pagamento.html', 
                         valor_inscricao=vlinscricao,
                         valor_taxa=vltaxa,
                         valor_total=valor_total)



@app.route('/gerar-pix', methods=['POST'])
def gerar_pix():
    try:
        data = request.get_json()
        # Round to 2 decimal places to avoid floating point precision issues
        valor_total = round(float(data.get('valor_total', 0)), 2)
        valor_atual = round(float(data.get('valor_atual', 0)), 2)
        valor_taxa = round(float(data.get('valor_taxa', 0)), 2)

        fn_camiseta(data.get('camiseta'))
        fn_apoio(data.get('apoio')) 
        fn_equipe(data.get('nome_equipe'))
        fn_integrantes(data.get('integrantes'))
        
        # Validate minimum transaction amount (Mercado Pago usually requires >= 1)
        if valor_total < 1:
            return jsonify({
                'success': False,
                'message': 'Valor mínimo da transação deve ser maior que R$ 1,00'
            }), 400
        
        print("=== DEBUG: Iniciando geração do PIX ===")
        print(f"Valor total recebido: {valor_total}")
        print(f"Valor atual: {valor_atual}")
        print(f"Valor taxa: {valor_taxa}")
        print(f"Token MP configurado: {os.getenv('MP_ACCESS_TOKEN')[:10]}...")
        print(f"CAMISA: {var_camiseta}")
        print(f"APOIO: {var_apoio}")
        print(f"EQUIPE: {var_equipe}")
        print(f"INTEGRANTES: {var_integrantes}")
        
        # Dados do pagador da sessão
        email = session.get('user_email')        
        nome_completo = session.get('user_name', '').split()
        cpf = session.get('user_cpf')

        #alimento essa variavel global var_email pra ser usada no evio do email 
        fn_email(email)
        
        print(f"Dados do pagador da sessão:")
        print(f"- Email: {email}")
        print(f"- Nome: {nome_completo}")
        print(f"- CPF: {cpf}")

        #Gerar referência externa única
        external_reference = str(uuid.uuid4())

        # Added required items structure
        preference_data = {
            "items": [{
                "id": "desafio200k_inscricao",
                "title": "Inscrição Desafio 200k",
                "description": "Inscrição para o 4º Desafio 200k",
                "category_id": "sports_tickets",
                "quantity": 1,
                "unit_price": valor_total
            }],
            "statement_descriptor": "DESAFIO200K"
        }
        
        preference_result = sdk.preference().create(preference_data)
        
        # Mantendo o payment_data original que já funcionava
        payment_data = {
            "transaction_amount": valor_total,
            "description": "Inscrição 4º Desafio 200k",
            "payment_method_id": "pix",
            "payer": {
                "email": email,
                "first_name": nome_completo[0] if nome_completo else "",
                "last_name": " ".join(nome_completo[1:]) if len(nome_completo) > 1 else "",
                "identification": {
                    "type": "CPF",
                    "number": re.sub(r'\D', '', cpf) if cpf else ""
                }   
            },
            "notification_url": "https://ecmrun.com.br/webhook",
            "external_reference": external_reference
        }
        
        payment_response = sdk.payment().create(payment_data)

        print("Dados do pagamento preparados:")
        print(json.dumps(payment_data, indent=2))

        # Criar pagamento no Mercado Pago
        print("Enviando requisição para o Mercado Pago...")
        payment_response = sdk.payment().create(payment_data)
        
        print("Resposta do Mercado Pago:")
        print(json.dumps(payment_response, indent=2))
        
        if not payment_response or "response" not in payment_response:
            print("Erro: Resposta do Mercado Pago inválida")
            return jsonify({
                'success': False,
                'message': 'Erro na resposta do Mercado Pago'
            }), 500

        payment = payment_response["response"]
        
        # Verificar a estrutura completa da resposta
        print("Estrutura da resposta payment:")
        print(json.dumps(payment, indent=2))
        
        # Verificar se há dados do PIX na resposta
        if "point_of_interaction" not in payment:
            print("Erro: point_of_interaction não encontrado na resposta")
            return jsonify({
                'success': False,
                'message': 'Dados do PIX não disponíveis - point_of_interaction não encontrado'
            }), 500
            
        if "transaction_data" not in payment["point_of_interaction"]:
            print("Erro: transaction_data não encontrado em point_of_interaction")
            return jsonify({
                'success': False,
                'message': 'Dados do PIX não disponíveis - transaction_data não encontrado'
            }), 500

        # Se chegou até aqui, retorna os dados do PIX
        return jsonify({
            'success': True,
            'qr_code': payment['point_of_interaction']['transaction_data']['qr_code'],
            'qr_code_base64': payment['point_of_interaction']['transaction_data']['qr_code_base64'],
            'payment_id': payment['id']
        })

    except Exception as e:
        print(f"=== ERRO CRÍTICO: ===")
        print(f"Tipo do erro: {type(e)}")
        print(f"Mensagem de erro: {str(e)}")
        print(f"Stack trace:")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'message': f'Erro ao gerar PIX: {str(e)}'
        }), 500


@app.route('/verificar-pagamento/<payment_id>')
def verificar_pagamento(payment_id):
    try:
        # Buscar o status diretamente do Mercado Pago
        payment_response = sdk.payment().get(payment_id)
        payment = payment_response["response"]
        
        print(f"Status do pagamento recebido: {payment['status']}")
        
        if payment["status"] == "approved":
            # Verificar se já não foi processado antes
            cur = mysql.connection.cursor()
            cur.execute("SELECT * FROM ecmrun.INSCRICAO_TT WHERE IDPAGAMENTO = %s", (payment_id,))
            existing_record = cur.fetchone()
            
            if not existing_record:
                # Calculate valor_pgto (total payment)
                valor = float(session.get('cat_vlinscricao', 0))
                taxa = float(session.get('cat_vltaxa', 0))
                valor_pgto = valor + taxa

                # Obtém a data e hora atuais
                data_e_hora_atual = datetime.now()
                # Define o fuso horário para Manaus
                fuso_horario = timezone('America/Manaus')
                # Converte a data e hora para o fuso horário de Manaus
                data_e_hora_manaus = data_e_hora_atual.astimezone(fuso_horario)
                # Formata a data e hora no formato desejado (dd/mm/yyyy hh:mm)
                data_pagamento = data_e_hora_manaus.strftime('%d/%m/%Y %H:%M')
                
                #data_pagamento = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                
                # Get additional data from session
                idatleta = session.get('user_idatleta')
                cpf = session.get('user_cpf')
                
                # Insert payment record
                query = """
                INSERT INTO ecmrun.INSCRICAO_TT (
                    IDATLETA, CPF, IDEVENTO, IDITEM, CAMISETA, APOIO, 
                    NOME_EQUIPE, INTEGRANTES, VALOR, TAXA, 
                    VALOR_PGTO, DTPAGAMENTO, STATUS, FORMAPGTO, 
                    IDPAGAMENTO, FLMAIL
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """
                
                params = (
                    idatleta,                            # IDATLETA
                    cpf,                                 # CPF
                    1,                                   # IDEVENTO (hardcoded as 1 for this event)
                    session.get('cat_iditem'),           # IDITEM
                    var_camiseta,                        # CAMISETA
                    var_apoio,                           # APOIO
                    var_equipe,                          # NOME_EQUIPE
                    var_integrantes,                     # INTEGRANTES
                    valor,                               # VALOR
                    taxa,                                # TAXA
                    valor_pgto,                          # VALOR_PGTO
                    data_pagamento,                      # DTPAGAMENTO
                    'CONFIRMADO',                        # STATUS
                    'PIX',                               # FORMAPGTO
                    payment_id,                          # IDPAGAMENTO
                    'N'
                )
                
                cur.execute(query, params)
                mysql.connection.commit()
                cur.close()
                
                print("Registro de pagamento inserido com sucesso!")
                
                return jsonify({
                    'success': True,
                    'status': 'approved',
                    'message': 'Pagamento processado e registrado'
                })
            else:
                print("Pagamento já processado anteriormente")
                return jsonify({
                    'success': True,
                    'status': 'approved',
                    'message': 'Pagamento já processado'
                })
        
        return jsonify({
            'success': True,
            'status': payment["status"]
        })
        
    except Exception as e:
        print(f"Erro ao verificar pagamento: {str(e)}")
        # Ensure JSON is returned even on error
        return jsonify({
            'success': False, 
            'message': str(e),
            'status': 'error'
        }), 500
    

# @app.route('/create-mercado-pago-payment', methods=['POST'])
# def create_mercado_pago_payment():
#     data = request.get_json()
    
#     preference_data = {
#         "items": data['items'],
#         "payment_methods": {
#             "excluded_payment_methods": [
#                 {"id": "ticket"},
#                 {"id": "bank_transfer"},
#                 {"id": "digital_wallet"},
#                 {"id": "prepaid_card"}
#             ],
#             "excluded_payment_types": [
#                 {"id": "ticket"},
#                 {"id": "bank_transfer"},
#                 {"id": "digital_wallet"}
#             ],
#             "installments": 3  # Optional: limit to single installment
#         },
#         "back_urls": {
#             "success": "http://192.168.1.21:5000/comprovante",
#             "failure": "http://192.168.1.21:5000/payment-failure",
#             "pending": "http://192.168.1.21:5000/payment-pending"
#         }
#     }
#    
#    preference_response = sdk.preference().create(preference_data)
#    return jsonify({
#        "init_point": preference_response["response"]["init_point"]
#    })


def gerar_link_pagamento():
    #sdk = mercadopago.SDK("YOUR_ACCESS_TOKEN")  # Substitua pelo seu token de acesso
    payment_data = {
        "items": [
            {"id": "1", "title": "Camisa", "quantity": 1, "currency_id": "BRL", "unit_price": 259.99}
        ],
        "back_urls": {
            "success": "http://127.0.0.1:5000/compracerta",
            "failure": "http://127.0.0.1:5000/compraerrada",
            "pending": "http://127.0.0.1:5000/compraerrada",
        },
        "auto_return": "all"
    }

    result = sdk.preference().create(payment_data)
    payment = result["response"]
    link_iniciar_pagamento = payment["init_point"]
    return link_iniciar_pagamento


@app.route('/create-mercado-pago-payment', methods=['POST'])
def create_mercado_pago_payment():
    data = request.get_json()
    
    payment_data = {
        "items": [
            {"id": "1", "title": "Teste", "quantity": 1, "currency_id": "BRL", "unit_price": 1.00}
        ],
        "back_urls": {
            "success": "http://192.168.100.16:5000/comprovante",
            "failure": "http://192.168.100.16:5000/compraerrada",
            "pending": "http://192.168.100.16:5000/compraerrada",
        },
        "auto_return": "all"
    }
    result = sdk.preference().create(payment_data)

    return jsonify({
        "init_point": result["response"]["init_point"]
    })



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
