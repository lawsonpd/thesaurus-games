from flask import Flask, render_template, request, jsonify, session, Response, render_template_string
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
    """Get a random word from the API with frequency filter"""
    url = f"https://{WORDS_API_HOST}/words/"
    headers = {
        "x-rapidapi-key": WORDS_API_KEY,
        "x-rapidapi-host": WORDS_API_HOST
    }
    
    try:
        params = {
            "random": "true",
            "hasDetails": "frequency,partOfSpeech",
            "frequencyMin": "3.0"
        }
        print(f"Requesting random word with params: {params}")
        response = requests.get(url, headers=headers, params=params)
        print(f"Random word response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            # Get all results that have synonyms
            results = [r for r in data.get('results', []) 
                      if r.get('synonyms') and r.get('partOfSpeech')]
            
            if not results:
                return None, None, None
                
            # Choose a random result that has synonyms
            result = random.choice(results)
            word = data.get('word')
            part_of_speech = result.get('partOfSpeech')
            synonyms = result.get('synonyms', [])
            
            print(f"Got word: {word} ({part_of_speech}) with synonyms: {synonyms}")
            return word, part_of_speech, synonyms
        else:
            print(f"Error getting random word: {response.text}")
            return None, None, None
    except Exception as e:
        print(f"Exception getting random word: {str(e)}")
        return None, None, None

def get_random_word_with_synonyms(min_synonyms=5):
    """Get a random word that has enough synonyms"""
    max_attempts_per_word = 5
    max_total_attempts = 20
    total_attempts = 0
    
    while total_attempts < max_total_attempts:
        for _ in range(max_attempts_per_word):
            total_attempts += 1
            word, part_of_speech, synonyms = get_random_word()
            if not word or not synonyms:
                continue
                
            if len(synonyms) >= min_synonyms:
                print(f"Found suitable word '{word}' ({part_of_speech}) with {len(synonyms)} synonyms")
                return word, synonyms, part_of_speech
            else:
                print(f"Skipping word '{word}' ({part_of_speech}) with only {len(synonyms)} synonyms")
        
        print(f"No suitable word found in batch, trying again...")
    
    print(f"Failed to find suitable word after {total_attempts} attempts")
    return None, None, None

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
    displayed = session.get('displayed_synonyms', [])
    all_synonyms = session.get('synonyms', [])
    remaining = [s for s in all_synonyms if s not in displayed]
    
    if not input_text.isalpha():
        return Response(
            render_template_string("""
                <div class="error-message">Please enter only alphabetic characters</div>
                <div class="guesses">
                    {% for guess in guesses %}
                        <span class="guess">{{ guess }}</span>
                    {% endfor %}
                </div>
            """, guesses=session.get('guesses', [])),
            headers={
                "HX-Trigger": "clearInput"
            }
        )
    
    # Store the guess in session
    guesses = session.get('guesses', [])
    guesses.append(input_text)
    session['guesses'] = guesses
    
    # Check if guess is a remaining synonym
    if input_text in remaining:
        # Move the synonym to displayed list
        remaining.remove(input_text)
        displayed.append(input_text)
        session['displayed_synonyms'] = displayed
        session['close_guess'] = input_text  # Mark this synonym for highlighting
        session.modified = True
        
        return Response(
            render_template_string("""
                <div id="input-result">
                    <div class="close-guess-message">Close guess!</div>
                    <div class="guesses">
                        {% for guess in guesses %}
                            <span class="guess">{{ guess }}</span>
                        {% endfor %}
                    </div>
                </div>
            """, guesses=guesses),
            headers={
                "HX-Trigger": ["clearInput", "refreshSynonyms"]
            }
        )
    
    session.modified = True
    
    if input_text == target_word:
        session['game_active'] = False
        session.modified = True
        return Response(
            render_template_string("""
            <!-- Display Area -->
            <div class="display-section">
                <div class="success-message">Congratulations! The word was '{{ target_word }}'</div>
                <div class="synonyms-container">
                    <div class="synonyms-column">
                        {% for word in displayed[::2] %}
                            <span class="synonym-word">{{ word }}</span>
                        {% endfor %}
                    </div>
                    <div class="synonyms-column">
                        {% for word in displayed[1::2] %}
                            <span class="synonym-word">{{ word }}</span>
                        {% endfor %}
                    </div>
                </div>
            </div>

            <!-- Input Area -->
            <div class="input-section">
                <div class="guesses">
                    <div class="success-message">Your guesses:</div>
                    {% for guess in guesses %}
                        <span class="guess">{{ guess }}</span>
                    {% endfor %}
                </div>
            </div>

            <!-- Game Control Section -->
            <div class="game-control-section">
                <div id="game-buttons">
                    <button class="game-button" 
                            hx-post="/api/toggle-game"
                            hx-target="#game-buttons"
                            hx-swap="innerHTML">
                        Start Game
                    </button>
                </div>
            </div>
            """, 
            target_word=target_word,
            guesses=guesses,
            displayed=displayed),
            headers={
                "HX-Retarget": "#game-area",
                "HX-Reswap": "innerHTML",
                "HX-Trigger": "clearInput"
            }
        )
    
    return Response(
        render_template_string("""
            <div class="error-message">Try again!</div>
            <div class="guesses">
                {% for guess in guesses %}
                    <span class="guess">{{ guess }}</span>
                {% endfor %}
            </div>
        """, guesses=guesses),
        headers={
            "HX-Trigger": "clearInput"
        }
    )

@app.route('/api/game-state', methods=['GET'])
def game_state():
    """API endpoint to manage game state and button rendering"""
    game_active = session.get('game_active', False)
    
    if game_active:
        return """
            <button class="game-button reset" 
                    hx-post="/api/toggle-game"
                    hx-target="#game-buttons"
                    hx-swap="innerHTML">
                Reset
            </button>
        """
    else:
        return """
            <button class="game-button" 
                    hx-post="/api/toggle-game"
                    hx-target="#game-buttons"
                    hx-swap="innerHTML">
                Start Game
            </button>
        """

@app.route('/api/toggle-game', methods=['POST'])
def toggle_game():
    """API endpoint to toggle game state"""
    was_active = session.get('game_active', False)
    
    if not was_active:  # Starting new game
        return Response(
            render_template_string("""
            <div id="game-area">
                <div class="rules-section">
                    <h2>Starting game...</h2>
                </div>
            </div>
            <script>
                htmx.ajax('POST', '/api/start-game', {
                    target: '#game-area',
                    swap: 'innerHTML'
                });
            </script>
            """)
        )
    else:  # Resetting game
        session.clear()
        session.modified = True
        return Response("""
            <!-- Rules Section -->
            <div class="rules-section">
                <h2>How to play:</h2>
                <p class="rules-text">
                    The goal is to guess the target word. Synonyms of the target word will be shown one after another. 
                    Guess the target word before you run out of clues!
                </p>
            </div>

            <!-- Game Control Section -->
            <div class="game-control-section">
                <div id="game-buttons">
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

@app.route('/api/start-game', methods=['POST'])
def start_game():
    """Initialize a new game"""
    target_word, synonyms, part_of_speech = get_random_word_with_synonyms()
    
    if not target_word or not synonyms:
        session.clear()
        session.modified = True
        return Response(
            render_template_string("""
                <div class="error-message">
                    Failed to start game. Could not find a suitable word. Please try again.
                </div>
                <div id="game-buttons">
                    <button class="game-button" 
                            hx-post="/api/toggle-game"
                            hx-target="#game-buttons"
                            hx-swap="innerHTML">
                        Start Game
                    </button>
                </div>
            """),
            headers={
                "HX-Retarget": "#game-area",
                "HX-Reswap": "innerHTML"
            }
        )
    
    # Set up new game state
    session['target_word'] = target_word
    session['synonyms'] = synonyms
    session['part_of_speech'] = part_of_speech
    session['displayed_synonyms'] = []
    session['game_active'] = True
    session['guesses'] = []
    session.modified = True
    
    # Return the initial game UI with the correct part of speech
    total_synonyms = len(synonyms)
    return Response(
        render_template_string("""
        <!-- Display Area -->
        <div class="display-section">
            <h2 class="section-heading">The target word part of speech is {{ part_of_speech }}</h2>
            <h2 class="section-heading">The synonyms are:</h2>
            <div id="display-area"
                 hx-trigger="load delay:100ms, every 4s"
                 hx-post="/api/next-synonym"
                 hx-swap="innerHTML">
                <div class="synonym-counter">Remaining clues: {{ total_synonyms }}</div>
                <div class="synonyms-container">
                </div>
            </div>
        </div>

        <!-- Game Status -->
        <div id="game-status"></div>

        <!-- Input Area -->
        <div class="input-section">
            <h2>Guess the common parent word</h2>
            <form hx-post="/api/process-input" 
                  hx-target="#input-result"
                  hx-on::after-request="this.reset()">
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
        """, 
        part_of_speech=part_of_speech,
        total_synonyms=total_synonyms),
        headers={
            "HX-Retarget": "#game-area",
            "HX-Reswap": "innerHTML"
        }
    )

@app.route('/api/next-synonym', methods=['POST'])
def next_synonym():
    """Get the next synonym to display"""
    if not session.get('game_active'):
        return "", 204
    
    all_synonyms = session.get('synonyms', [])
    displayed = session.get('displayed_synonyms', [])
    close_guess = session.get('close_guess', None)
    target_word = session.get('target_word', '')
    remaining_count = len(all_synonyms) - len(displayed)
    
    # Check for game over condition first
    if len(displayed) >= len(all_synonyms):
        session['game_active'] = False
        session.modified = True
        return Response(
            render_template_string("""
                <div class="game-over-message">
                    Game Over! The word was '{{ target_word }}'
                </div>
                <div>The synonyms were:</div>
                <div class="synonyms-container">
                    <div class="synonyms-column">
                        {% for word in displayed[::2] %}
                            <span class="synonym-word">{{ word }}</span>
                        {% endfor %}
                    </div>
                    <div class="synonyms-column">
                        {% for word in displayed[1::2] %}
                            <span class="synonym-word">{{ word }}</span>
                        {% endfor %}
                    </div>
                </div>
                <div id="game-buttons">
                    <button class="game-button" 
                            hx-post="/api/toggle-game"
                            hx-target="#game-buttons"
                            hx-swap="innerHTML">
                        Start Game
                    </button>
                </div>
            """, 
            displayed=displayed,
            target_word=target_word),
            headers={
                "HX-Reswap": "innerHTML",
                "HX-Retarget": "#game-area"
            }
        )
    
    # Get next synonym if not showing a close guess
    if not close_guess:
        remaining = [s for s in all_synonyms if s not in displayed]
        next_syn = random.choice(remaining)
        displayed.append(next_syn)
        session['displayed_synonyms'] = displayed
        session.modified = True
    else:
        # Clear the close guess flag after showing it once
        session['close_guess'] = None
        session.modified = True
    
    # Create two-column layout with synonyms
    return Response(
        render_template_string("""
            <div class="synonym-counter">Remaining clues: {{ remaining }}</div>
            <div class="synonyms-container">
                <div class="synonyms-column">
                    {% for word in displayed[::2] %}
                        <span class="synonym-word {% if word == close_guess %}close-guess{% endif %}">
                            {{ word }}
                        </span>
                    {% endfor %}
                </div>
                <div class="synonyms-column">
                    {% for word in displayed[1::2] %}
                        <span class="synonym-word {% if word == close_guess %}close-guess{% endif %}">
                            {{ word }}
                        </span>
                    {% endfor %}
                </div>
            </div>
            <script>
                document.getElementById('input-result').innerHTML = `
                    <div class="guesses">
                        {% for guess in session.get('guesses', []) %}
                            <span class="guess">{{ guess }}</span>
                        {% endfor %}
                    </div>
                `;
            </script>
        """, 
        displayed=displayed, 
        remaining=remaining_count - (0 if close_guess else 1),
        close_guess=close_guess),
        headers={
            "HX-Reswap": "innerHTML",
            "HX-Retarget": "#display-area"
        }
    )

if __name__ == '__main__':
    app.run(debug=True) 