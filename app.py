from flask import Flask, render_template, request, jsonify, session, Response
import requests
import random
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

WORDS_API_HOST = "wordsapiv1.p.rapidapi.com"
WORDS_API_KEY = os.getenv('RAPIDAPI_KEY')

print(f"API Key loaded: {'*' * len(WORDS_API_KEY) if WORDS_API_KEY else 'None'}")  # Debug log - masks the key

def get_random_word():
    """Get a random word from the API"""
    url = f"https://{WORDS_API_HOST}/words/"
    headers = {
        "x-rapidapi-key": WORDS_API_KEY,
        "x-rapidapi-host": WORDS_API_HOST
    }
    
    try:
        print(f"Requesting random word with headers: {headers}")  # Debug log
        response = requests.get(url + "?random=true", headers=headers)
        print(f"Random word response status: {response.status_code}")  # Debug log
        print(f"Random word response: {response.text}")  # Debug log
        
        if response.status_code == 200:
            word = response.json().get('word')
            print(f"Got word: {word}")  # Debug log
            return word
        else:
            print(f"Error getting random word: {response.text}")  # Debug log
            return None
    except Exception as e:
        print(f"Exception getting random word: {str(e)}")  # Debug log
        return None

def get_synonyms(word):
    """Get synonyms for a given word"""
    url = f"https://{WORDS_API_HOST}/words/{word}/synonyms"
    headers = {
        "x-rapidapi-key": WORDS_API_KEY,
        "x-rapidapi-host": WORDS_API_HOST
    }
    
    try:
        print(f"Requesting synonyms for word: {word}")  # Debug log
        response = requests.get(url, headers=headers)
        print(f"Synonyms response status: {response.status_code}")  # Debug log
        print(f"Synonyms response: {response.text}")  # Debug log
        
        if response.status_code == 200:
            synonyms = response.json().get('synonyms', [])
            print(f"Got synonyms: {synonyms}")  # Debug log
            return synonyms
        else:
            print(f"Error getting synonyms: {response.text}")  # Debug log
            return []
    except Exception as e:
        print(f"Exception getting synonyms: {str(e)}")  # Debug log
        return []

def get_random_word_with_synonyms(max_attempts=5):
    """Get a random word that has synonyms"""
    for _ in range(max_attempts):
        word = get_random_word()
        if not word:
            continue
            
        synonyms = get_synonyms(word)
        if synonyms:  # Only return if we found synonyms
            return word, synonyms
            
    return None, None

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
    """Process user's word guess"""
    if not session.get('game_active'):
        return jsonify({"status": "error", "message": "No active game"})
    
    input_text = request.form.get('text', '').lower()
    target_word = session.get('target_word', '').lower()
    
    if not input_text.isalpha():
        return jsonify({
            "status": "error",
            "message": "Please enter only alphabetic characters"
        })
    
    if input_text == target_word:
        session['game_active'] = False
        return jsonify({
            "status": "win",
            "message": f"Congratulations! The word was '{target_word}'"
        })
    
    return jsonify({
        "status": "wrong",
        "message": "Try again!"
    })

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
        # Clear game state when resetting
        session.pop('target_word', None)
        session.pop('synonyms', None)
        session.pop('displayed_synonyms', None)
        return Response("""
            <!-- Display Area -->
            <div class="display-section">
                <h2>The words that share a common synonym are:</h2>
                <div id="display-area" class="text-area">
                    <div class="default-message">Play the Thesaurus Game</div>
                </div>
            </div>

            <!-- Game Status -->
            <div id="game-status"></div>

            <!-- Input Area -->
            <div class="input-section">
                <h2>Guess the common parent word</h2>
                <form hx-post="/api/process-input" 
                      hx-target="#input-result">
                    <input type="text" 
                           name="text" 
                           placeholder="Enter text here..."
                           pattern="[A-Za-z]+"
                           title="Please enter only alphabetic characters"
                           required>
                    <button type="submit">Submit</button>
                </form>
                <div id="input-result"></div>
            </div>

            <!-- Game Control Section -->
            <div class="game-control-section">
                <div id="game-buttons" 
                     hx-get="/api/game-state" 
                     hx-trigger="load">
                    <button class="game-button" 
                            hx-post="/api/toggle-game"
                            hx-target="#game-buttons"
                            hx-swap="innerHTML">
                        Start Game
                    </button>
                </div>
            </div>
            """,
            headers={
                "HX-Retarget": "#game-area",
                "HX-Reswap": "innerHTML"
            }
        )
    else:
        # Start new game
        return Response("""
            <!-- Display Area -->
            <div class="display-section">
                <h2>The words that share a common synonym are:</h2>
                <div id="display-area" class="text-area"
                     hx-trigger="load delay:100ms, every 4s"
                     hx-post="/api/next-synonym"
                     hx-swap="innerHTML">
                </div>
            </div>

            <!-- Game Status -->
            <div id="game-status"></div>

            <!-- Input Area -->
            <div class="input-section">
                <h2>Guess the common parent word</h2>
                <form hx-post="/api/process-input" 
                      hx-target="#input-result">
                    <input type="text" 
                           name="text" 
                           placeholder="Enter text here..."
                           pattern="[A-Za-z]+"
                           title="Please enter only alphabetic characters"
                           required>
                    <button type="submit">Submit</button>
                </form>
                <div id="input-result"></div>
            </div>

            <!-- Game Control Section -->
            <div class="game-control-section">
                <div id="game-buttons">
                    <button class="game-button reset" 
                            hx-post="/api/toggle-game"
                            hx-target="#game-buttons"
                            hx-swap="innerHTML">
                        Reset
                    </button>
                </div>
            </div>
            <script>
                htmx.ajax('POST', '/api/start-game', {target:'#game-status'});
            </script>
            """,
            headers={
                "HX-Retarget": "#game-area",
                "HX-Reswap": "innerHTML"
            }
        )

@app.route('/api/start-game', methods=['POST'])
def start_game():
    """Initialize a new game"""
    target_word, synonyms = get_random_word_with_synonyms()
    print(f"Got word: {target_word} with synonyms: {synonyms}")  # Debug log
    
    if not target_word or not synonyms:
        return jsonify({
            "error": "Could not find a suitable word with synonyms. Please try again."
        }), 500
    
    # Store game state in session
    session.clear()  # Clear any existing session data
    session['target_word'] = target_word
    session['synonyms'] = synonyms
    session['displayed_synonyms'] = []
    session['game_active'] = True
    session.modified = True  # Ensure session is saved
    
    print(f"Session state after start: {dict(session)}")  # Debug log
    
    return jsonify({
        "status": "success",
        "message": "Game started"
    })

@app.route('/api/next-synonym', methods=['POST'])
def next_synonym():
    """Get the next synonym to display"""
    if not session.get('game_active'):
        return "", 204  # No content response to stop polling
    
    all_synonyms = session.get('synonyms', [])
    displayed = session.get('displayed_synonyms', [])
    
    if len(displayed) >= 10 or len(displayed) >= len(all_synonyms):
        session['game_active'] = False
        session.modified = True
        # Send HX-Trigger to update game state
        return Response(
            "Game Over! Too many synonyms displayed.",
            headers={
                "HX-Trigger": "gameStateChange"
            }
        )
    
    # Get next synonym
    remaining = [s for s in all_synonyms if s not in displayed]
    next_syn = random.choice(remaining)
    displayed.append(next_syn)
    session['displayed_synonyms'] = displayed
    session.modified = True
    
    # Return just the text content
    current_display = "\n".join(displayed)
    return current_display

if __name__ == '__main__':
    app.run(debug=True) 