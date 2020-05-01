import sys, os, lucene, threading, time

import json
from os import listdir, path
from java.nio.file import Paths
from org.apache.lucene.analysis.miscellaneous import LimitTokenCountAnalyzer
from org.apache.lucene.analysis.standard import StandardAnalyzer
from org.apache.lucene.document import Document, Field, FieldType
from org.apache.lucene.index import FieldInfo, IndexWriter, IndexWriterConfig, IndexOptions, DirectoryReader
from org.apache.lucene.store import SimpleFSDirectory
from org.apache.lucene.search import IndexSearcher
from org.apache.lucene.queryparser.classic import QueryParser
import nltk
from nltk.collocations import *

lucene.initVM(vmargs=['-Djava.awt.headless=true'])

class Ticker(object):
    def __init__(self):
        self.tick = True

    def run(self):
        while self.tick:
            sys.stdout.write('.')
            sys.stdout.flush()
            time.sleep(1.0)
            
"""
This class is loosely based on the Lucene (java implementation) demo class
org.apache.lucene.demo.IndexFiles.  It will take a directory as an argument
and will index all of the files in that directory and downward recursively.
It will index on the file path, the file name and the file contents.  The
resulting Lucene index will be placed in the current directory and called
'index'.                                                                                                                      
"""
class IndexFiles(object):
    """Usage: python IndexFiles <doc_directory>"""
    def __init__(self, root, storeDir, analyzer):
        if not os.path.exists(storeDir):
            os.mkdir(storeDir)

        store = SimpleFSDirectory(Paths.get(storeDir))
        config = IndexWriterConfig(analyzer)
        config.setOpenMode(IndexWriterConfig.OpenMode.CREATE)
        writer = IndexWriter(store, config)

        self.indexDocs(root, writer)
        ticker = Ticker()
        print('commit index',)
        threading.Thread(target=ticker.run).start()
        writer.commit()
        writer.close()
        ticker.tick = False
        print('done')
        
    def indexDocs(self, root, writer):
        t1 = FieldType()
        t1.setStored(True)
        t1.setTokenized(False)
        t1.setIndexOptions(IndexOptions.DOCS_AND_FREQS)

        t2 = FieldType()
        t2.setStored(False)
        t2.setTokenized(True)
        t2.setIndexOptions(IndexOptions.DOCS_AND_FREQS_AND_POSITIONS)
        
        for root, dirnames, filenames in os.walk(root):
            for filename in filenames:
                if not filename.endswith('.txt'):
                    continue
                print("adding %s" % filename)
                try:
                    path = os.path.join(root, filename)
                    file = open(path)
                    contents = file.read()
                    file.close()
                    doc = Document()
                    doc.add(Field("name", filename, t1))
                    doc.add(Field("path", root, t1))
                    if len(contents) > 0:
                        doc.add(Field("contents", contents, t2))
                    else:
                        print("warning: no content in %s" % filename)
                    writer.addDocument(doc)
                except Exception as e:
                    print("Failed in indexDocs: %s" % e)

def search_loop(index_dir, field="contents", explain=False):
    searcher = IndexSearcher(DirectoryReader.open(SimpleFSDirectory(Paths.get(index_dir))))
    analyzer = StandardAnalyzer()
    print("Hit enter with no input to quit.")
    while True:
        command = input("Query:")
        if command == '':
            return
        print("Searching for: %s" % command)
        query = QueryParser(field, analyzer).parse(command)
        scoreDocs = searcher.search(query, 50).scoreDocs
        print("%s total matching documents." % len(scoreDocs))

        for scoreDoc in scoreDocs:
            doc = searcher.doc(scoreDoc.doc)
            if field == 'web':
                print(f'{doc.get("web")} | {doc.get("raw")} | {scoreDoc.score}')
            else:
                print('path:', doc.get("path"), 'name:', doc.get("name"))
            if explain:
                explanation = searcher.explain(query, scoreDoc.doc)
                print(explanation)
                print('------------')                    

class IndexDataframe(object):
    def __init__(self, df, storeDir, analyzer, quiet=False):
        if not os.path.exists(storeDir):
            os.mkdir(storeDir)

        self.bigram_set, self.trigram_set = make_ngrams()
        store = SimpleFSDirectory(Paths.get(storeDir))
        config = IndexWriterConfig(analyzer)
        config.setOpenMode(IndexWriterConfig.OpenMode.CREATE)
        writer = IndexWriter(store, config)

        self.indexDocs(df, writer, quiet)
        ticker = Ticker()
        if not quiet:
            print('commit index',)
        threading.Thread(target=ticker.run).start()
        writer.commit()
        writer.close()
        ticker.tick = False
        print('done')
        
    def indexDocs(self, df, writer, quiet):
        t1 = FieldType()
        t1.setStored(True)
        t1.setTokenized(False)
        t1.setIndexOptions(IndexOptions.DOCS_AND_FREQS)

        t2 = FieldType()
        t2.setStored(True)
        t2.setTokenized(True)
        t2.setIndexOptions(IndexOptions.DOCS_AND_FREQS_AND_POSITIONS)
        
        for row in df.iterrows():
            raw, web, id = (row[1]['raw'], row[1]['web'], row[1]['id'])
            if not quiet:
                print("adding %s" % web)
            try:
                # mash subsentences
                # Example: 'the quick brown' => 'thequickbrown quickbrown brown'
                # This enables wildcard matching on subsentences
                # E.g. 'the private select' => 'theprivateselect privateselect select'
                #   matching 'p*r*s*l*' matches 'privateselect'
                mashed_terms = []
                web_words = [normalize_word(word) for word in web.split()]
                for i in range(len(web_words)):
                    mashed = ''.join(web_words[i:])
                    mashed_terms.append(mashed)                
                mashed_web = ' '.join(mashed_terms)
                # if a bigram contains a unigram, elliminate it from web
                # if a trigram contains a bigram, eliminate it from bigram
                bigrams = collect_bigrams(web_words, self.bigram_set)
                trigrams = collect_trigrams(web_words, self.trigram_set)
                unigrams = web_words[:]
                unigram_positions_to_eliminate = set()
                eliminate_unigrams_from_trigrams(unigrams, trigrams, unigram_positions_to_eliminate)
                eliminate_unigrams_from_bigrams(unigrams, bigrams, unigram_positions_to_eliminate)
                #unigrams = eliminate_unigrams(unigrams, unigram_positions_to_eliminate)
                #bigrams = eliminate_bigrams_from_trigrams(bigrams, trigrams)
                unigrams = ' '.join(unigrams)
                bigrams = ' '.join(bigrams)
                trigrams = ' '.join(trigrams)
                ngrams = ' '.join([unigrams, bigrams, trigrams])
                
                doc = Document()
                doc.add(Field("raw", raw, t1))
                doc.add(Field("web", web, t2))
                doc.add(Field("mashed_web", mashed_web, t2))
                doc.add(Field("unigrams", unigrams, t2))
                doc.add(Field("bigrams", bigrams, t2))
                doc.add(Field("trigrams", trigrams, t2))
                doc.add(Field("ngrams", ngrams, t2))
                # doc.add(Field("ngrams1", ngrams, t2))
                # doc.add(Field("ngrams2", ngrams, t2))
                # doc.add(Field("ngrams3", ngrams, t2))
                # doc.add(Field("ngrams4", ngrams, t2))
                # doc.add(Field("ngrams5", ngrams, t2))
                # doc.add(Field("ngrams6", ngrams, t2))
                doc.add(Field("id", id, t1))
                writer.addDocument(doc)
            except Exception as e:
                print("Failed in indexDocs: %s" % e)
        

def filter_unigrams(sent, bigrams):
    """
    Eliminate all bigrams from sent
    bigrams is a list of the form w1_w2
    """
    pass

def normalize_word(word):
    import re
    word = word.lower()
    p = re.compile('[^a-z-]')
    word = p.sub('', word)
    return word.strip()            


def make_dictionary(df):
    """
    Extract all tokens from 'web' column of 'df'.
    Return set of tokens
    """
    result = set()
    for sent in df.web.unique():
        for word in sent.split():
            nword = normalize_word(word)
            if nword:
                result.add(nword)
    return result


def make_raw_to_web(df):
    from collections import defaultdict
    raw_to_web = defaultdict(list)
    for row in df.iterrows():
        raw, web = (row[1]['raw'], row[1]['web'])
        raw_to_web[raw].append(web)
    return raw_to_web

class QueryMaker:
    def make_query(raw):
        pass

class SimpleQueryMaker(QueryMaker):
    def make_query(self, raw):
        return raw

class Searcher:
    def search(self, query):
        pass

class SimpleSearcher(Searcher):
    def __init__(self, index_dir):
        self.searcher = IndexSearcher(DirectoryReader.open(SimpleFSDirectory(Paths.get(index_dir))))
        self.analyzer = StandardAnalyzer()

    def search(self, qstring):
        query = QueryParser("web", self.analyzer).parse(qstring)
        scoreDocs = self.searcher.search(query, 50).scoreDocs
        return [self.searcher.doc(score_doc.doc) for score_doc in scoreDocs]

    def explain(self, qstring):
        query = QueryParser("web", self.analyzer).parse(qstring)
        score_docs = self.searcher.search(query, 50).scoreDocs
        print(qstring)
        for score_doc in score_docs:
            doc = self.searcher.doc(score_doc.doc)
            print(f'{doc.get("web")} | {doc.get("raw")} | {score_doc.score}')
            explanation = self.searcher.explain(query, score_doc.doc)
            print(explanation)
            print('------------')                    

class Config:
    def __init__(self, query_maker, searcher):
        self.query_maker = query_maker
        self.searcher = searcher


def is_hit(raw, config, raw_to_web):
    query = config.query_maker.make_query(raw)
    docs = config.searcher.search(query)
    if not docs:
        return False
    top_doc = docs[0]
    top_web = top_doc.get('web')
    if raw not in raw_to_web:
        return False
    web_candidates = raw_to_web[raw]
    if top_web not in web_candidates:
        return False
    return True

def evaluate(queries, config, raw_to_web):
    num_queries = len(queries)
    total_hits = 0
    missed_queries = []
    for query in queries:
        if is_hit(query, config, raw_to_web):
            total_hits += 1
        else:
            missed_queries.append(query)
    precision = total_hits/num_queries
    return precision, missed_queries


def make_wildcard_query(q, known_words):
    words = q.split()
    nwords = [normalize_word(word) for word in words]
    tokens = []
    for nword in nwords:
        if nword not in known_words:
            wild_word = ''
            for c in nword:
                wild_word += c + '*'
            tokens.append(wild_word)
        else:
            tokens.append(nword)
    return ' '.join(tokens)                        


def make_mashed_wildcard_query(q, known_words):
    words = q.split()
    nwords = [normalize_word(word) for word in words]
    tokens = []
    for nword in nwords:
        if nword not in known_words:
            wild_word = ''
            for c in nword:
                wild_word += c + '*'
            tokens.append('mashed_web:' + wild_word)
        else:
            tokens.append(nword)
    return ' '.join(tokens)                        


def make_ngram_wildcard_query(q, known_words):
    words = q.split()
    nwords = [normalize_word(word) for word in words]
    tokens = []
    for nword in nwords:
        if nword not in known_words:
            wild_word = ''
            for c in nword:
                wild_word += c + '*'
            tokens.append('web:' + wild_word)
            tokens.append('bigrams:' + wild_word)
            tokens.append('trigrams:' + wild_word)
        else:
            tokens.append(nword)
    return ' '.join(tokens)                        


def make_xor_ngram_wildcard_query(q, known_words):
    words = q.split()
    nwords = [normalize_word(word) for word in words]
    tokens = []
    for nword in nwords:
        if nword not in known_words:
            wild_word = ''
            for c in nword:
                wild_word += c + '*'
            tokens.append('(web:' + wild_word + ' bigrams:' + wild_word + ' trigrams:' + wild_word + ')')
        #     tokens.append('(+web:' + wild_word + ' -bigrams:' + wild_word + ' -trigrams:' + wild_word + ')')
        #     tokens.append('(-web:' + wild_word + ' +bigrams:' + wild_word + ' -trigrams:' + wild_word + ')')
        #     tokens.append('(-web:' + wild_word + ' -bigrams:' + wild_word + ' +trigrams:' + wild_word + ')')
        else:
            tokens.append(nword)
    return ' OR '.join(tokens)                        


def make_boosted_ngram_wildcard_query(q, known_words):
    words = q.split()
    nwords = [normalize_word(word) for word in words]
    tokens = []
    i = 0
    for nword in nwords:
        if nword not in known_words:
            i += 1
            wild_word = ''
            for c in nword:
                wild_word += c + '*'
#            tokens.append('ngrams:' + wild_word)
#            tokens.append(f'ngrams{i}:' + wild_word)
            tokens.append(f'ngrams:' + wild_word)
            # tokens.append('(unigrams:' + wild_word + '^1.0 bigrams:' + wild_word + '^1.0 trigrams:' + wild_word + '^1.0)')
        #     tokens.append('(+web:' + wild_word + ' -bigrams:' + wild_word + ' -trigrams:' + wild_word + ')')
        #     tokens.append('(-web:' + wild_word + ' +bigrams:' + wild_word + ' -trigrams:' + wild_word + ')')
        #     tokens.append('(-web:' + wild_word + ' -bigrams:' + wild_word + ' +trigrams:' + wild_word + ')')
        else:
            tokens.append(nword + '^1.0')
    return ' OR '.join(tokens)                        




class WildQueryMaker(QueryMaker):
    def __init__(self, words):
        self.words = words
        
    def make_query(self, raw):
        return make_wildcard_query(raw, self.words)


class MashedWildQueryMaker(QueryMaker):
    def __init__(self, words):
        self.words = words
        
    def make_query(self, raw):
        return make_mashed_wildcard_query(raw, self.words)
    

class NgramWildQueryMaker(QueryMaker):
    def __init__(self, words):
        self.words = words
        
    def make_query(self, raw):
        return make_ngram_wildcard_query(raw, self.words)
    

class XorNgramWildQueryMaker(QueryMaker):
    def __init__(self, words):
        self.words = words
        
    def make_query(self, raw):
        return make_xor_ngram_wildcard_query(raw, self.words)
    

class BoostedNgramWildQueryMaker(QueryMaker):
    def __init__(self, words):
        self.words = words
        
    def make_query(self, raw):
        return make_boosted_ngram_wildcard_query(raw, self.words)
    

def make_fuzzy_mashed_wildcard_query(q, known_words):
    words = q.split()
    nwords = [normalize_word(word) for word in words]
    tokens = []
    for nword in nwords:
        if nword not in known_words:
            wild_word = ''
            for c in nword:
                wild_word += c + '*'
            # wildcard version of word
            tokens.append('mashed_web:' + wild_word)
            # fuzzy version of word
            tokens.append(nword + '~')
        else:
            tokens.append(nword)
    return ' '.join(tokens)                        
    

class FuzzyMashedWildQueryMaker(QueryMaker):
    def __init__(self, words):
        self.words = words
        
    def make_query(self, raw):
        return make_fuzzy_mashed_wildcard_query(raw, self.words)
    

class ReceiptIter:
    def __init__(self):
        self.data_path = '/home/ubuntu/XCS224U-Project/data/raw_web_joined'
        
    def __iter__(self):
        for fname in listdir(self.data_path):
            file_path = path.join(self.data_path, fname)
            with open(file_path, 'r') as f:                
                receipts = json.load(f)
                for receipt in receipts:
                    web_sent = [normalize_word(w) for w in receipt['web'].lower().split() if normalize_word(w) not in ['-', '']]
                    yield web_sent
                    raw_sent = [normalize_word(w) for w in receipt['raw'].lower().split() if normalize_word(w) not in ['-', '']]
                    yield raw_sent

def make_ngrams():
    """
    Return (bigrams, trigrams): sets of collocated bigrams and trigrams
    """
    bigram_measures = nltk.collocations.BigramAssocMeasures()
    trigram_measures = nltk.collocations.TrigramAssocMeasures()
    sents = [sent for sent in ReceiptIter()]
    web_sents = sents[::2]
    words = [item for sublist in web_sents for item in sublist]
    bigram_finder = BigramCollocationFinder.from_words(words)
    bigram_finder.apply_freq_filter(3)
    bigram_scored_pmi = bigram_finder.score_ngrams(bigram_measures.pmi)
    bigrams = [bigram for score, bigram in sorted([(score, bigram) for bigram, score in bigram_scored_pmi], reverse=True)]
    bigram_set = set(bigrams)
    trigram_finder = TrigramCollocationFinder.from_words(words)
    trigram_finder.apply_freq_filter(3)
    trigram_scored_pmi = trigram_finder.score_ngrams(trigram_measures.pmi)
    trigrams = [trigram for score, trigram in sorted([(score, trigram) for trigram, score in trigram_scored_pmi], reverse=True)]
    trigram_set = set(trigrams)
    return (bigram_set, trigram_set)


def collect_bigrams(sent, bigram_set):
    res = []
    for i in range(len(sent)-1):
        candidate = tuple(sent[i:i+2])
        if candidate in bigram_set:
            res.append('_'.join((candidate)))
    return res


def collect_trigrams(sent, trigram_set):
    res = []
    for i in range(len(sent)-2):
        candidate = tuple(sent[i:i+3])
        if candidate in trigram_set:
            res.append('_'.join((candidate)))
    return res
                       
def eliminate_unigrams_from_trigrams(sentence, trigrams, unigram_positions_to_eliminate):
    trigram_set = set([tuple(trigram.split('_')) for trigram in trigrams])
    for i in range(len(sentence) - 2):
        candidate = (sentence[i], sentence[i+1], sentence[i+2])
        if candidate in trigram_set:
            unigram_positions_to_eliminate.add(i)
            unigram_positions_to_eliminate.add(i+1)
            unigram_positions_to_eliminate.add(i+2)

def eliminate_unigrams_from_bigrams(sentence, bigrams, unigram_positions_to_eliminate):
    bigram_set = set([tuple(bigram.split('_')) for bigram in bigrams])
    for i in range(len(sentence) - 1):
        candidate = (sentence[i], sentence[i+1])
        if candidate in bigram_set:
            unigram_positions_to_eliminate.add(i)
            unigram_positions_to_eliminate.add(i+1)


def eliminate_bigrams_from_trigrams(bigrams, trigrams):
    bigram_set = set(bigrams)
    bigrams_to_eliminate = set()
    for trigram in trigrams:
        t0, t1, t2 = trigram.split('_')
        candidate1 = t0 + "_" + t1
        candidate2 = t1 + "_" + t2
        if candidate1 in bigram_set:
            bigrams_to_eliminate.add(candidate1)
        if candidate2 in bigram_set:
            bigrams_to_eliminate.add(candidate2)
    new_bigrams = list(bigram_set - bigrams_to_eliminate)
    return new_bigrams


def eliminate_unigrams(sentence, positions_to_eliminate):
    new_sentence = []
    for i, word in enumerate(sentence):
        if i not in positions_to_eliminate:
            new_sentence.append(word)
    return new_sentence
