from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/load-more')
def load_more():
    # Example endpoint for HTMX to call
    return "<div>More content loaded!</div>"

if __name__ == '__main__':
    app.run(debug=True) 