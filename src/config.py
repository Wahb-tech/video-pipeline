CATEGORIES = {
    "yacht": ["luxury yacht mediterranean", "super yacht sea", "yacht party adults"],
    "pool": ["luxury infinity pool adult woman", "resort pool adult woman", "rooftop pool luxury"],
    "dubai": ["dubai skyline luxury", "dubai rooftop night", "dubai downtown luxury"],
    "supercar": ["luxury supercar night", "lamborghini city", "sports car luxury"],
    "private_jet": ["private jet luxury", "private aircraft interior", "luxury aviation"],
    "villa": ["luxury villa pool", "modern mansion sunset", "luxury penthouse"],
    "beach": ["luxury beach resort adults", "adult woman beach resort", "tropical luxury beach"],
    "nightlife": ["luxury rooftop party adults", "nightclub luxury adults", "champagne nightlife"],
    "watch": ["luxury watch wrist", "luxury watch car", "expensive watch lifestyle"],
    "cash": ["counting cash money dark", "luxury cash money aesthetic", "money counting night"],
    "business": ["businessman luxury dark", "man suit luxury night", "wealth lifestyle man dark"],
    "hotel": ["luxury hotel lobby", "five star hotel room", "luxury resort"],
    "monaco": ["monaco luxury yacht", "monaco supercar", "french riviera luxury"],
    "restaurant": ["luxury restaurant rooftop", "fine dining luxury", "rooftop dinner city"]
}

DARK_QUERIES = {
    "yacht": ["luxury yacht night dark", "super yacht night cinematic", "yacht party night luxury"],
    "pool": ["luxury pool night dark", "rooftop pool night luxury", "infinity pool night adult woman"],
    "dubai": ["dubai night luxury dark", "dubai rooftop night cinematic", "dubai supercar night"],
    "supercar": ["black supercar night", "luxury car dark parking", "supercar tunnel night cinematic"],
    "private_jet": ["private jet night luxury", "private jet interior dark", "luxury aviation night"],
    "villa": ["luxury villa night dark", "mansion night cinematic", "penthouse night luxury"],
    "beach": ["luxury beach night resort", "night beach club luxury", "dark tropical resort night"],
    "nightlife": ["dark luxury nightlife", "luxury rooftop night adults", "exclusive club dark cinematic"],
    "watch": ["luxury watch dark aesthetic", "expensive watch low light", "watch wrist dark luxury"],
    "cash": ["counting money dark aesthetic", "cash money dark luxury", "money luxury low light"],
    "business": ["wealthy man dark luxury", "man suit black luxury", "businessman night cinematic"],
    "hotel": ["dark luxury hotel", "five star hotel night", "luxury lobby low light"],
    "monaco": ["monaco supercar night", "monaco luxury night", "monaco yacht night"],
    "restaurant": ["dark luxury restaurant", "rooftop restaurant night luxury", "fine dining low light cinematic"]
}

STYLE_PRESETS = {
    "dark_luxury": ["supercar", "cash", "watch", "business", "dubai", "nightlife", "restaurant", "private_jet", "hotel"],
    "summer_luxury": ["pool", "beach", "yacht", "monaco", "villa", "restaurant"],
    "dubai": ["dubai", "supercar", "pool", "restaurant", "hotel", "private_jet", "nightlife"],
    "yacht_life": ["yacht", "beach", "pool", "monaco", "nightlife", "villa"],
    "mixed": list(CATEGORIES.keys())
}

THEME_PRESETS = {
    "dark_cars": ["supercar", "supercar", "dubai", "watch", "business", "nightlife", "hotel"],
    "money": ["cash", "cash", "watch", "business", "supercar", "restaurant", "hotel"],
    "dark_life": ["business", "nightlife", "restaurant", "hotel", "dubai", "private_jet", "watch"],
    "mixed_dark": STYLE_PRESETS["dark_luxury"]
}

COPY_VARIANTS = {
    "one_day": "One day.",
    "soon": "Soon.",
    "none": ""
}

CAPTION_TEMPLATES = {
    "choice": {
        "dark_cars": ["Ferrari or Lamborghini?", "Night drive or showroom?", "Black or red?"],
        "money": ["The watch or the car first?", "Freedom or status?", "Cash or assets?"],
        "dark_life": ["Dubai or Monaco?", "Rooftop or private jet?", "Nightlife or silence?"],
        "mixed_dark": ["Dubai or Monaco?", "Car or watch first?", "Freedom or status?"]
    },
    "aspiration": {
        "dark_cars": ["What is the first car on your list?", "How close are you?", "What are you building toward?"],
        "money": ["What does made it look like to you?", "How close are you?", "What are you building toward?"],
        "dark_life": ["What does freedom look like to you?", "Where would you wake up first?", "What are you building toward?"],
        "mixed_dark": ["What does made it look like to you?", "How close are you?", "What are you building toward?"]
    },
    "minimal": {
        "dark_cars": ["Built in silence.", "One day.", "Soon."],
        "money": ["Different standards.", "One day.", "Soon."],
        "dark_life": ["Built for more.", "One day.", "Soon."],
        "mixed_dark": ["Built in silence.", "One day.", "Soon."]
    }
}

FALLBACK_TEXTS = list(COPY_VARIANTS.values())

BASELINE = {
    "style": "dark_luxury",
    "duration": 25.0,
    "clips": 17,
    "bpm": 100.0,
    "text_position": "center"
}
