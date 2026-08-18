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

@app.route('/visaogeral')
def visao_geral():
    return render_template('VisaoGeral.html')

if __name__ == '__main__':
    app.run(debug=True)