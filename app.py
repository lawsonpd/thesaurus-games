from flask import Flask, render_template, request, jsonify, session, Response, render_template_string
import requests
import random
import os
from dotenv import load_dotenv
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from threading import Lock
import time

load_dotenv()  # Load environment variables

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

WORDS_API_HOST = "wordsapiv1.p.rapidapi.com"
WORDS_API_KEY = os.getenv('RAPIDAPI_KEY')

print(f"API Key loaded: {'*' * len(WORDS_API_KEY) if WORDS_API_KEY else 'None'}")  # Debug log - masks the key

# Global cache and lock
word_cache = []
cache_lock = Lock()

async def fetch_word_async(session):
    """Async function to fetch a random word"""
    url = f"https://{WORDS_API_HOST}/words/"
    headers = {
        "x-rapidapi-key": WORDS_API_KEY,
        "x-rapidapi-host": WORDS_API_HOST
    }
    params = {
        "random": "true",
        "hasDetails": "frequency,partOfSpeech",
        "frequencyMin": "4.0"
    }
    
    try:
        # Try up to 3 times per word
        for _ in range(3):
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    word = data.get('word')
                    
                    # Get word details
                    details_url = f"https://{WORDS_API_HOST}/words/{word}"
                    async with session.get(details_url, headers=headers) as details_response:
                        if details_response.status == 200:
                            details = await details_response.json()
                            results = details.get('results', [])
                            
                            results_with_synonyms = [r for r in results 
                                                   if r.get('synonyms') and r.get('partOfSpeech')]
                            
                            if results_with_synonyms:
                                result = max(results_with_synonyms, 
                                          key=lambda x: len(x.get('synonyms', [])))
                                synonyms = result.get('synonyms', [])
                                
                                if len(synonyms) >= 5:
                                    return {
                                        'word': word,
                                        'part_of_speech': result.get('partOfSpeech'),
                                        'synonyms': synonyms
                                    }
            
            # Small delay between attempts
            await asyncio.sleep(0.1)
        
        return None
    except Exception as e:
        print(f"Error in fetch_word_async: {str(e)}")
        return None

async def fetch_multiple_words_async(count=5):
    """Async function to fetch multiple words"""
    async with aiohttp.ClientSession() as session:
        tasks = []
        # Request 4x the number we need to ensure we get enough valid ones
        for _ in range(count * 4):
            tasks.append(fetch_word_async(session))
        
        results = await asyncio.gather(*tasks)
        valid_words = [word for word in results if word is not None]
        
        # Remove duplicates
        seen = set()
        unique_words = []
        for word in valid_words:
            if word['word'] not in seen:
                seen.add(word['word'])
                unique_words.append(word)
        
        return unique_words[:count]

def start_async_cache_update(count=5):
    """Start async word fetching in a background thread"""
    async def update_cache():
        words = await fetch_multiple_words_async(count)
        with cache_lock:
            global word_cache
            word_cache.extend(words)
            print(f"Added {len(words)} words to global cache. New size: {len(word_cache)}")
    
    def run_async():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(update_cache())
        loop.close()
    
    # Run in a separate thread
    executor = ThreadPoolExecutor(max_workers=1)
    executor.submit(run_async)

def ensure_word_cache(session):
    """Ensure we have enough words in the cache"""
    global word_cache
    
    with cache_lock:
        cache_size = len(word_cache)
        print(f"\nChecking word cache. Current size: {cache_size}")
    
    try:
        if cache_size == 0:
            print("Cache empty. Getting initial word...")
            max_attempts = 10  # Increase max attempts
            for attempt in range(max_attempts):
                word_data = get_random_word()
                if word_data[0]:  # If we got a valid word
                    with cache_lock:
                        word_cache = [{
                            'word': word_data[0],
                            'part_of_speech': word_data[1],
                            'synonyms': word_data[2]
                        }]
                    print(f"Got initial word on attempt {attempt + 1}")
                    # Start async cache population after setting initial word
                    start_async_cache_update(10)
                    return True
                print(f"Failed to get initial word, attempt {attempt + 1}/{max_attempts}")
            
            print("Failed to get initial word after all attempts")
            return False
            
        elif cache_size <= 5:
            print(f"Cache low ({cache_size} words). Adding 5 more...")
            start_async_cache_update(5)
        
        return True
        
    except Exception as e:
        print(f"Error in ensure_word_cache: {str(e)}")
        return False

def get_random_word():
    """Get a random word from the API synchronously"""
    url = f"https://{WORDS_API_HOST}/words/"
    headers = {
        "x-rapidapi-key": WORDS_API_KEY,
        "x-rapidapi-host": WORDS_API_HOST
    }
    params = {
        "random": "true",
        "hasDetails": "frequency,partOfSpeech",
        "frequencyMin": "4.0"
    }
    
    try:
        # Try up to 3 times to get a word with enough synonyms
        for _ in range(3):
            response = requests.get(url, headers=headers, params=params)
            print(f"API Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                word = data.get('word')
                print(f"Word data: {word}")
                
                # Try to get word directly with details
                details_url = f"https://{WORDS_API_HOST}/words/{word}"
                details_response = requests.get(details_url, headers=headers)
                
                if details_response.status_code == 200:
                    details = details_response.json()
                    results = details.get('results', [])
                    print(f"Results count: {len(results)}")
                    
                    # Get all results that have synonyms
                    results_with_synonyms = [r for r in results 
                                           if r.get('synonyms') and r.get('partOfSpeech')]
                    
                    if results_with_synonyms:
                        # Choose result with most synonyms
                        result = max(results_with_synonyms, 
                                   key=lambda x: len(x.get('synonyms', [])))
                        synonyms = result.get('synonyms', [])
                        
                        if len(synonyms) >= 5:
                            return word, result.get('partOfSpeech'), synonyms
            
            # Small delay between attempts
            time.sleep(0.1)
        
        return None, None, None
    except Exception as e:
        print(f"Exception getting random word: {str(e)}")
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
        # Add word to successful guesses
        session['correct_words'].append({
            'word': target_word,
            'round': session['current_round']
        })
        session['current_round'] += 1
        session.modified = True
        
        return Response(
            render_template_string("""
            <!-- Display Area -->
            <div class="display-section">
                <div class="round-summary">Round {{ current_round - 1 }} completed!</div>
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
                    <button class="game-button next-round" 
                            hx-post="/api/start-game"
                            hx-target="#game-area"
                            hx-swap="innerHTML">
                        Next Round
                    </button>
                </div>
            </div>
            """, 
            target_word=target_word,
            guesses=guesses,
            displayed=displayed,
            current_round=session['current_round']),
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
        # Clear everything except word cache
        word_cache = session.get('word_cache', [])
        session.clear()
        session['word_cache'] = word_cache  # Restore word cache
        session.modified = True
        
        return Response(
            render_template_string("""
            <div class="loading-message">
                <h2>Starting game...</h2>
                <p>Retrieving words...</p>
                <div class="loading-spinner"></div>
            </div>
            <script>
                htmx.ajax('POST', '/api/start-game', {
                    target: '#game-area',
                    swap: 'innerHTML'
                });
            </script>
            """),
            headers={
                "HX-Retarget": "#game-area",
                "HX-Reswap": "innerHTML"
            }
        )
    else:  # Resetting game
        session.clear()  # This will clear everything including word cache
        session.modified = True
        return Response(
            render_template_string("""
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
            """),
            headers={
                "HX-Retarget": "#game-area",
                "HX-Reswap": "innerHTML"
            }
        )

@app.route('/api/start-game', methods=['POST'])
def start_game():
    """Initialize a new game"""
    global word_cache
    
    # Check cache at the start of each round
    if not ensure_word_cache(session):
        return Response(
            render_template_string("""
                <div class="rules-section">
                    <div class="error-message">
                        Failed to retrieve enough words. Please try again.
                    </div>
                    <div id="game-buttons">
                        <button class="game-button" 
                                hx-post="/api/toggle-game"
                                hx-target="#game-buttons"
                                hx-swap="innerHTML">
                            Try Again
                        </button>
                    </div>
                </div>
            """),
            headers={
                "HX-Retarget": "#game-area",
                "HX-Reswap": "innerHTML"
            }
        )
    
    # Get the next word from the cache
    with cache_lock:
        word_data = word_cache.pop(0)
    print(f"\nUsing word from cache: {word_data['word']}")
    print(f"Cache size after pop: {len(word_cache)}")

    target_word = word_data['word']
    synonyms = word_data['synonyms']
    part_of_speech = word_data['part_of_speech']
    
    # Set up new game state
    session['target_word'] = target_word
    session['synonyms'] = synonyms
    session['part_of_speech'] = part_of_speech
    session['displayed_synonyms'] = []
    session['game_active'] = True
    session['guesses'] = []
    
    # Initialize multi-round stats if not exists
    if 'correct_words' not in session:
        session['correct_words'] = []
        session['current_round'] = 1
    
    session.modified = True
    
    # Return the initial game UI without rules section
    total_synonyms = len(synonyms)
    return Response(
        render_template_string("""
        <!-- Game Area -->
        <div class="game-container">
            <!-- Display Area -->
            <div class="display-section">
                <h2 class="section-heading">The target word part of speech is {{ part_of_speech }}</h2>
                <h2 class="section-heading">The synonyms are:</h2>
                <div id="display-area"
                     hx-trigger="load delay:100ms, every 7s"
                     hx-post="/api/next-synonym"
                     hx-swap="innerHTML">
                    <div class="synonyms-container">
                    </div>
                    <div class="synonym-counter">Remaining clues: {{ total_synonyms }}</div>
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
        correct_words = session.get('correct_words', [])
        final_round = session.get('current_round', 1)
        session.modified = True
        
        return Response(
            render_template_string("""
                <div class="game-over-message">
                    Game Over! The word was '{{ target_word }}'
                </div>
                <div class="game-stats">
                    <h3>Final Score</h3>
                    <p>You correctly guessed {{ correct_words|length }} words:</p>
                    <ul class="word-list">
                        {% for entry in correct_words %}
                            <li>Round {{ entry.round }}: {{ entry.word }}</li>
                        {% endfor %}
                    </ul>
                </div>
                <div>The synonyms for the final word were:</div>
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
                        Start New Game
                    </button>
                </div>
            """, 
            displayed=displayed,
            target_word=target_word,
            correct_words=correct_words),
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
            <div class="synonym-counter">Remaining clues: {{ remaining }}</div>
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