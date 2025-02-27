from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import spacy

# 加载spaCy的英语模型

nlp = spacy.load('en_core_web_sm')

class SimilarityCalculator_BERT:
    def __init__(self):
        self.model = SentenceTransformer('bert-base-nli-mean-tokens')

    def calc_similarity(self, s1, s2):
        doc = nlp(s1)
        filtered_words = [token.text for token in doc if token.pos_ != 'ADJ']
        s1 = ' '.join(filtered_words)
        if len(s1.split()) >= 2 and len(s2.split()) >= 2:
            s1, s2 = remove_common_nouns_of_length_one(s1, s2)
        s1_embedding = self.model.encode(s1)
        s2_embedding = self.model.encode(s2)
        score = cosine_similarity([s1_embedding], [s2_embedding])[0][0]

        return score

def get_nouns(phrase):
    doc = nlp(phrase)
    nouns = [token.text for token in doc if token.pos_ == "NOUN"]
    return nouns

def remove_common_nouns_of_length_one(phrase1, phrase2):
    nouns1 = get_nouns(phrase1)
    nouns2 = get_nouns(phrase2)
    common_nouns = set(nouns1).intersection(set(nouns2))
    if len(common_nouns) == 1:
        for noun in common_nouns:
            phrase1 = phrase1.replace(noun, '')
            phrase2 = phrase2.replace(noun, '')
        phrase1 = " ".join(phrase1.split())
        phrase2 = " ".join(phrase2.split())

    return phrase1.strip(), phrase2.strip()
