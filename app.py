from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('HOME.html')

@app.route('/login')
def login():
    return render_template('LOGIN.html')

@app.route('/recursos')
def recursos():
    return render_template('RECURSOS.html')

@app.route('/sobrenos')
def sobrenos():
    return render_template('SOBRENOS.html')

@app.route('/solicitar-acesso')
def solicitar_acesso():
    return render_template('SOLICITAR_ACESSO.html')

@app.route('/solicitar-acesso/enviado')
def solicitar_acesso_enviado():
    return render_template('SOLICITACAO_ENVIADA.html')

@app.route('/visaogeral')
def visao_geral():
    return render_template('VisaoGeral.html')

@app.route('/inventario')
def inventario():
    return render_template('INVENTARIO.html')

@app.route('/inventario/gerenciar')
def inventario_gerenciar():
    return render_template('GERENCIAR_PECA.html')

@app.route('/salas')
def salas():
    return render_template('SALAS.html')

@app.route('/salas/gerenciar')
def salas_gerenciar():
    return render_template('GERENCIAR_SALA.html')

@app.route('/requisicoes')
def requisicoes():
    return render_template('REQUISICOES.html')

@app.route('/logs')
def logs():
    return render_template('LOGS.html')

@app.route('/usuarios')
def usuarios():
    return render_template('USUARIOS.html')

@app.route('/backup')
def backup():
    return render_template('BACKUP.html')

if __name__ == '__main__':
    app.run(debug=True)
