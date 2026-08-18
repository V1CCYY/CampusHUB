from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def home():
    # O Flask procura automaticamente na pasta 'templates'
    return render_template('HOME.html')

@app.route('/login')
def login():
    return render_template('LOGIN.html')

@app.route('/recursos')
def recursos():
    return render_template('RECURSOS.html')

if __name__ == '__main__':
    app.run(debug=True)