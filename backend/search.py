knowledge_base = [
    {
        "title": "Boss Location",
        "content": "The boss is located in the northern fortress beyond the desert canyon."
    },
    {
        "title": "Healing Items",
        "content": "You can find healing herbs near riverbanks and forest edges."
    },
    {
        "title": "Fast Travel",
        "content": "Fast travel unlocks after discovering major towns and activating their shrines."
    }
]


def search_knowledge_base(query):
    query = query.lower()
    results = []

    for item in knowledge_base:
        text = f"{item['title']} {item['content']}".lower()
        if any(word in text for word in query.split()):
            results.append(item)

    return results