# world/pool_loader.py
"""
YAML pool loading utility.
Loads description pools from YAML files in world/data/pools/.
"""

import yaml
import os
import random
from django.conf import settings


POOL_CACHE = {}
POOL_BASE = getattr(settings, 'POOL_BASE_PATH', 'world/data/pools')


def load_pool(category, name, use_cache=True):
    """
    Load a YAML pool file and return its contents as a dict.
    
    Args:
        category (str): Subdirectory — e.g. "wisp", "moods", "furniture"
        name (str): Filename without extension — e.g. "base", "melancholy"
        use_cache (bool): Whether to cache the loaded pool
        
    Returns:
        dict: Pool contents, or empty dict if file not found
    """
    cache_key = f"{category}/{name}"
    
    if use_cache and cache_key in POOL_CACHE:
        return POOL_CACHE[cache_key]
    
    # Build path relative to game directory
    game_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(game_dir, POOL_BASE, category, f"{name}.yaml")
    
    if not os.path.exists(path):
        return {}
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        print(f"[POOL LOADER] Error loading {path}: {e}")
        return {}
    
    if use_cache:
        POOL_CACHE[cache_key] = data
    
    return data


def reload_pool(category, name):
    """Force reload a pool, bypassing cache."""
    cache_key = f"{category}/{name}"
    if cache_key in POOL_CACHE:
        del POOL_CACHE[cache_key]
    return load_pool(category, name, use_cache=True)


def reload_all_pools():
    """Clear the entire pool cache, forcing reload on next access."""
    POOL_CACHE.clear()


def pick_from_pool(category, name, key, context=None):
    """
    Pick a random line from a specific pool key.
    
    Args:
        category (str): Pool category
        name (str): Pool name
        key (str): Key within the pool (e.g. "ambient", "room_desc")
        context (dict): Optional substitution variables
        
    Returns:
        str: A random line from the pool, with context substituted
        None: If pool or key not found
    """
    data = load_pool(category, name)
    pool = data.get(key, [])
    
    if not pool:
        return None
    
    line = random.choice(pool)
    
    if context:
        line = substitute(line, context)
    
    return line


def substitute(text, context):
    """
    Substitute {variable} placeholders in text.
    
    Args:
        text (str): Text with {variable} placeholders
        context (dict): Substitution values
        
    Returns:
        str: Text with substitutions applied
    """
    for key, value in context.items():
        text = text.replace(f"{{{key}}}", str(value))
        # Also handle {Key} with capital first letter
        cap_key = key[0].upper() + key[1:] if key else key
        text = text.replace(f"{{{cap_key}}}", str(value).capitalize())
    
    return text


def apply_pool_to_object(obj, category, pool_name):
    """
    Load a pool and apply its contents to a game object's db attributes.
    
    Args:
        obj: Evennia object to apply pool to
        category (str): Pool category
        pool_name (str): Pool name
    """
    data = load_pool(category, pool_name)
    if not data:
        return False
    
    obj.db.pool_name = pool_name
    obj.db.pool_category = category
    obj.db.room_desc_pools = data.get('room_desc', {})
    obj.db.ambient_pools = data.get('ambient', {})
    obj.db.examine_descs = data.get('examine', {})
    obj.db.body_language_pool = data.get('body_language_pool', [])
    obj.db.interaction_results = data.get('interaction_results', {})
    obj.db.consent_required = data.get('metadata', {}).get(
        'consent_required', []
    )
    
    return True
