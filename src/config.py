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
    "restaurant": ["luxury restaurant rooftop", "fine dining luxury", "rooftop dinner city"],
    "dark_feminine": ["adult woman luxury nightlife", "adult woman elegant resort", "adult woman yacht party"]
}

DARK_QUERIES = {
    "yacht": ["superyacht at night cinematic", "luxury yacht marina night", "black yacht night"],
    "dubai": ["Dubai skyline night luxury", "Burj Khalifa night cinematic", "Dubai supercar night"],
    "supercar": ["black Lamborghini night cinematic", "black Ferrari night luxury", "supercar tunnel night"],
    "private_jet": ["private jet cabin dark luxury", "private jet runway night", "luxury jet interior cinematic"],
    "villa": ["luxury mansion night cinematic", "modern villa night luxury", "dark penthouse interior"],
    "watch": ["Rolex watch dark cinematic", "luxury watch macro black", "expensive watch low light"],
    "cash": ["counting hundred dollar bills dark", "cash stacks black background", "money safe dark cinematic"],
    "hotel": ["five star hotel lobby dark", "luxury hotel suite night", "dark marble hotel interior"]
}

STYLE_PRESETS = {
    "dark_luxury": ["supercar", "cash", "watch", "dubai", "private_jet", "villa", "hotel", "yacht"],
    "summer_luxury": ["pool", "beach", "yacht", "monaco", "villa", "restaurant"],
    "dubai": ["dubai", "supercar", "pool", "restaurant", "hotel", "private_jet", "nightlife"],
    "yacht_life": ["yacht", "beach", "pool", "monaco", "nightlife", "villa"],
    "mixed": list(CATEGORIES.keys())
}

THEME_PRESETS = {
    "dark_cars": ["supercar", "supercar", "dubai", "watch", "private_jet", "hotel", "villa"],
    "money": ["cash", "cash", "watch", "supercar", "private_jet", "hotel", "villa"],
    "dark_life": ["hotel", "villa", "dubai", "private_jet", "watch", "yacht", "supercar"],
    "mixed_dark": STYLE_PRESETS["dark_luxury"]
}

COPY_VARIANTS = {
    "one_day": "One day.",
    "soon": "Soon.",
    "built_silence": "Built in silence.",
    "different_standard": "Different standards.",
    "no_plan_b": "No plan B.",
    "earned_not_given": "Earned. Not given.",
    "one_goal": "One goal.",
    "destiny": "Destiny.",
    "end_goal": "The end goal.",
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
