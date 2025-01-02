import pytest
import asyncio
from unittest.mock import Mock, patch
import sys
from pathlib import Path

# Add the parent directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from app import (
    app, 
    get_random_word, 
    fetch_word_async, 
    fetch_multiple_words_async,
    ensure_word_cache
)

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def mock_word_response():
    return {
        'word': 'test',
        'results': [{
            'partOfSpeech': 'noun',
            'synonyms': ['exam', 'trial', 'assessment', 'evaluation', 'examination']
        }]
    }

@pytest.fixture
def mock_session():
    return {}

def test_get_random_word(mock_word_response):
    """Test synchronous word fetching"""
    with patch('requests.get') as mock_get:
        # Mock the API responses
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_word_response
        
        word, pos, synonyms = get_random_word()
        
        assert word == 'test'
        assert pos == 'noun'
        assert len(synonyms) == 5
        assert 'exam' in synonyms

def test_get_random_word_no_synonyms():
    """Test handling of words without enough synonyms"""
    with patch('requests.get') as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            'word': 'test',
            'results': [{
                'partOfSpeech': 'noun',
                'synonyms': ['exam']  # Not enough synonyms
            }]
        }
        
        word, pos, synonyms = get_random_word()
        assert word is None
        assert pos is None
        assert synonyms is None

@pytest.mark.asyncio
async def test_fetch_word_async(mock_word_response):
    """Test async word fetching"""
    async def mock_get(*args, **kwargs):
        mock_response = Mock()
        mock_response.status = 200
        
        async def mock_json():
            return mock_word_response
            
        mock_response.json = mock_json
        return mock_response
    
    session = Mock()
    session.get = mock_get
    
    result = await fetch_word_async(session)
    
    assert result['word'] == 'test'
    assert result['part_of_speech'] == 'noun'
    assert len(result['synonyms']) == 5

@pytest.mark.asyncio
async def test_fetch_multiple_words_async():
    """Test fetching multiple words asynchronously"""
    mock_responses = [
        {
            'word': f'test{i}',
            'results': [{
                'partOfSpeech': 'noun',
                'synonyms': [f'syn{j}' for j in range(5)]
            }]
        } for i in range(3)
    ]
    
    async def mock_get(*args, **kwargs):
        mock_response = Mock()
        mock_response.status = 200
        
        async def mock_json():
            return mock_responses.pop(0)
            
        mock_response.json = mock_json
        return mock_response
    
    async with patch('aiohttp.ClientSession') as mock_session:
        mock_session.return_value.__aenter__.return_value.get = mock_get
        
        results = await fetch_multiple_words_async(count=2)
        
        assert len(results) == 2
        assert results[0]['word'] == 'test0'
        assert len(results[0]['synonyms']) == 5

def test_ensure_word_cache(mock_session):
    """Test cache management"""
    with patch('app.get_random_word') as mock_get_word:
        mock_get_word.return_value = ('test', 'noun', ['syn1', 'syn2', 'syn3', 'syn4', 'syn5'])
        
        result = ensure_word_cache(mock_session)
        
        assert result is True
        assert len(mock_session.get('word_cache', [])) > 0

def test_game_start(client):
    """Test game initialization endpoint"""
    with patch('app.ensure_word_cache') as mock_ensure_cache:
        mock_ensure_cache.return_value = True
        
        response = client.post('/api/start-game')
        
        assert response.status_code == 200
        assert b'target word part of speech' in response.data

def test_game_over(client):
    """Test game over state"""
    with client.session_transaction() as session:
        session['game_active'] = True
        session['target_word'] = 'test'
        session['synonyms'] = ['syn1', 'syn2', 'syn3']
        session['displayed_synonyms'] = ['syn1', 'syn2', 'syn3']
    
    response = client.post('/api/next-synonym')
    
    assert response.status_code == 200
    assert b'Game Over' in response.data 