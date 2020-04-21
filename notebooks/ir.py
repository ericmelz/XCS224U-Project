import sys, os, lucene, threading, time

from java.nio.file import Paths
from org.apache.lucene.analysis.miscellaneous import LimitTokenCountAnalyzer
from org.apache.lucene.analysis.standard import StandardAnalyzer
from org.apache.lucene.document import Document, Field, FieldType
from org.apache.lucene.index import FieldInfo, IndexWriter, IndexWriterConfig, IndexOptions, DirectoryReader
from org.apache.lucene.store import SimpleFSDirectory
from org.apache.lucene.search import IndexSearcher
from org.apache.lucene.queryparser.classic import QueryParser

lucene.initVM(vmargs=['-Djava.awt.headless=true'])

class Ticker(object):
    def __init__(self):
        self.tick = True

    def run(self):
        while self.tick:
            sys.stdout.write('.')
            sys.stdout.flush()
            time.sleep(1.0)
            
"""                                                                                                                        This class is loosely based on the Lucene (java implementation) demo class                                                 org.apache.lucene.demo.IndexFiles.  It will take a directory as an argument                                                and will index all of the files in that directory and downward recursively.                                                It will index on the file path, the file name and the file contents.  The                                                  resulting Lucene index will be placed in the current directory and called                                                  'index'.                                                                                                                      
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

def search_loop(index_dir, field="contents"):
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
                    

class IndexDataframe(object):
    def __init__(self, df, storeDir, analyzer, quiet=False):
        if not os.path.exists(storeDir):
            os.mkdir(storeDir)

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
                web_words = web.split()
                for i in range(len(web_words)):
                    mashed = ''.join(web_words[i:])
                    mashed_terms.append(mashed)                
                mashed_web = ' '.join(mashed_terms)
                
                doc = Document()
                doc.add(Field("raw", raw, t1))
                doc.add(Field("web", web, t2))
                doc.add(Field("mashed_web", mashed_web, t2))
                doc.add(Field("id", id, t1))
                writer.addDocument(doc)
            except Exception as e:
                print("Failed in indexDocs: %s" % e)
        

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
    

