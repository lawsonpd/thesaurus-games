from flask import Flask, render_template, request, jsonify, session

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Required for session management

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

@app.route('/api/game-state', methods=['GET'])
def game_state():
    """API endpoint to manage game state and button rendering"""
    game_active = session.get('game_active', False)
    
    if game_active:
        button_html = """
            <button class="game-button reset" 
                    hx-post="/api/toggle-game"
                    hx-target="#game-buttons"
                    hx-swap="innerHTML">
                Reset
            </button>
        """
    else:
        # When game is inactive, update both the button and display area
        button_html = f"""
            <button class="game-button" 
                    hx-post="/api/toggle-game"
                    hx-target="#game-buttons"
                    hx-swap="innerHTML">
                Start Game
            </button>
            <script>
                document.getElementById('display-area').innerHTML = 
                    '<div class="default-message">Play the Thesaurus Game</div>';
            </script>
        """
    return button_html

@app.route('/api/toggle-game', methods=['POST'])
def toggle_game():
    """API endpoint to toggle game state"""
    was_active = session.get('game_active', False)
    session['game_active'] = not was_active
    
    if was_active:
        # Clear the display area when resetting
        return game_state() + """
            <script>
                document.getElementById('display-area').innerHTML = 
                    '<div class="default-message">Play the Thesaurus Game</div>';
            </script>
        """
    else:
        # Clear the display area when starting
        return game_state() + """
            <script>
                document.getElementById('display-area').innerHTML = '';
                document.getElementById('input-result').innerHTML = '';
            </script>
        """
    return game_state()

if __name__ == '__main__':
    app.run(debug=True) 