from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/load-more')
def load_more():
    return "<div>More content loaded!</div>"

@app.route('/commonality', methods=['GET'])
def commonality():
    return render_template('commonality.html')

@app.route('/api/display-text', methods=['POST'])
def display_text():
    """API endpoint for displaying text in the upper text area"""
    text = request.form.get('display_text', 'Default text')
    return f"<div>{text}</div>"

@app.route('/api/process-input', methods=['POST'])
def process_input():
    """API endpoint for processing user input from the text field"""
    input_text = request.form.get('text', '')
    if input_text.isalpha():
        response = {"status": "success", "message": f"Received: {input_text}"}
    else:
        response = {"status": "error", "message": "Please enter only alphabetic characters"}
    return jsonify(response)

if __name__ == '__main__':
    app.run(debug=True) 