GENDER_EMOJIS = {
    "action": "💥",
    "acción": "💥",
    "adventure": "🌄",
    "aventura": "🌄",
    "animation": "🎨",
    "animación": "🎨",
    "comedy": "😂",
    "comedia": "😂",
    "crime": "🔪",
    "crimen": "🔪",
    "documentary": "📹",
    "documental": "📹",
    "drama": "😭",
    "family": "👨‍👩‍👧‍👦",
    "familia": "👨‍👩‍👧‍👦",
    "fantasy": "🧙‍♀️",
    "fantasía": "🧙‍♀️",
    "history": "📜",
    "historia": "📜",
    "horror": "👻",
    "terror": "👻",
    "music": "🎵",
    "música": "🎵",
    "mystery": "🕵️‍♂️",
    "misterio": "🕵️‍♂️",
    "romance": "❤️",
    "science fiction": "👽",
    "sci-fi": "👽",
    "ciencia ficción": "👽",
    "sports": "⚽",
    "deportes": "⚽",
    "thriller": "🥶",
    "suspense": "🥶",
    "war": "🪖",
    "guerra": "🪖",
    "western": "🌵"
}

def format_genres_with_emojis(genres_string: str) -> str:
    if not genres_string or genres_string == "N/A":
        return "🎭 N/A"

    genres_list = [g.strip() for g in genres_string.split(",")]
    
    formatted_genres = []
    
    for genre in genres_list:
        emoji = GENDER_EMOJIS.get(genre.lower(), "")
        
        if emoji:
            formatted_genres.append(f"{emoji} {genre}")
        else:
            formatted_genres.append(genre)
            
    return ", ".join(formatted_genres)