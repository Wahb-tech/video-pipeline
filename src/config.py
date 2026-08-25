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
    "hotel": ["five star hotel lobby dark", "luxury hotel suite night", "dark marble hotel interior"],
    "dark_feminine": [
        "elegant woman black dress luxury car night",
        "woman private jet dark luxury",
        "woman penthouse night cinematic",
        "elegant woman luxury hotel night",
        "woman bikini superyacht night luxury",
        "woman luxury villa pool night dark",
        "woman short evening dress supercar night"
    ]
}

STYLE_PRESETS = {
    "dark_luxury": ["supercar", "cash", "watch", "dubai", "private_jet", "villa", "hotel", "yacht", "dark_feminine"],
    "summer_luxury": ["pool", "beach", "yacht", "monaco", "villa", "restaurant"],
    "dubai": ["dubai", "supercar", "pool", "restaurant", "hotel", "private_jet", "nightlife"],
    "yacht_life": ["yacht", "beach", "pool", "monaco", "nightlife", "villa"],
    "mixed": list(CATEGORIES.keys())
}

THEME_PRESETS = {
    "dark_cars": ["supercar", "supercar", "dubai", "watch", "private_jet", "hotel", "villa", "dark_feminine"],
    "money": ["cash", "cash", "watch", "supercar", "private_jet", "hotel", "villa", "dark_feminine"],
    "dark_life": ["hotel", "villa", "dubai", "private_jet", "watch", "yacht", "supercar", "dark_feminine"],
    "mixed_dark": STYLE_PRESETS["dark_luxury"]
}

COPY_VARIANTS = {
    "pov_relationship": [
        "POV: She wants double texts. You want double the income.",
        "POV: She asks why you reply late. You're busy building what they said you couldn't.",
        "POV: She wants your attention. Your future needs it more.",
        "POV: They call you distant. You're just closer to your goals.",
        "POV: Dating can wait. The vision can't.",
        "She asked what matters more. You showed her the blueprint.",
        "Too focused to explain the silence.",
        "Her type was available. Your type is unstoppable."
    ],
    "future_self": [
        "POV: Your future self finally recognizes you.",
        "POV: You became everything you used to scroll past.",
        "POV: This is why you didn't quit.",
        "POV: The life in your head became your address.",
        "Your current pain is funding this version of you.",
        "One day, the vision stops being a vision.",
        "Build until your old dreams look small.",
        "The future is watching what you do tonight."
    ],
    "silent_revenge": [
        "POV: They stopped laughing when it started working.",
        "POV: No announcement. Just a different lifestyle.",
        "They ignored the plan. They won't ignore the result.",
        "The comeback doesn't need a caption.",
        "Let the upgrade answer every question.",
        "Revenge, but make it look like discipline.",
        "You said less. The results said enough.",
        "They'll call it luck because they missed the sacrifice."
    ],
    "obsession": [
        "POV: You stopped chasing people and started chasing impossible goals.",
        "POV: Your obsession finally became visible.",
        "Not motivated. Possessed by the vision.",
        "Normal goals never kept you awake.",
        "You don't need balance when you're building the escape.",
        "Some call it unhealthy. You call it unfinished.",
        "The goal got louder than every distraction.",
        "Comfort became the only thing you feared."
    ],
    "standards": [
        "POV: Your standards became more expensive than your excuses.",
        "POV: You outgrew every room that doubted you.",
        "High standards. Higher goals.",
        "You weren't asking for too much. You were asking the wrong life.",
        "A different life requires a different standard.",
        "Stop shrinking the dream to fit the room.",
        "Average was never part of the plan.",
        "Your taste is a preview, not a fantasy."
    ],
    "discipline": [
        "POV: Nobody clapped for the nights that built this.",
        "POV: You worked while they waited for motivation.",
        "Discipline bought what motivation kept promising.",
        "The boring days paid for the unforgettable ones.",
        "You don't rise to the dream. You fall to the routine.",
        "Private discipline. Public difference.",
        "Your habits are already choosing your lifestyle.",
        "The price was consistency. Most people walked away."
    ],
    "minimal": [
        "Built in silence.",
        "No plan B.",
        "Earned. Not given.",
        "Different standards.",
        "One goal.",
        "The end goal."
    ],
    "none": [""]
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

FALLBACK_TEXTS = [text for variants in COPY_VARIANTS.values() for text in variants]

BASELINE = {
    "style": "dark_luxury",
    "duration": 25.0,
    "clips": 17,
    "bpm": 100.0,
    "text_position": "center"
}
