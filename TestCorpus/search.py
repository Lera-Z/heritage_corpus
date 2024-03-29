# coding=utf-8
__author__ = 'elmira'

import re
import codecs
from collections import defaultdict
from db_utils import Database
from annotator.models import Document, Sentence, Annotation, Token, Morphology
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q

# todo make this into a neat one-line js-function
jquery = """jQuery(function ($) {$('#***').annotator().annotator('addPlugin', 'Tags').annotator('addPlugin', 'Corr').annotator('addPlugin', 'Correction', 'Enter correct variant...').annotator('addPlugin', 'ReadOnlyAnnotations').annotator('addPlugin', 'Store', {prefix: '/heritage_corpus/document-annotations',annotationData: {'document': ***},loadFromSearch: {'document': ***}});});"""
reg = re.compile(',| ')
regToken= re.compile('">(.*?)</span>', flags=re.U | re.DOTALL)
regSpans = re.compile('[.?,!:«(;#№–/...)»-]*<span .*?</span>[.?,!:«(;#№–/...)»-]*', flags=re.U | re.DOTALL)


class ShowSentence:
    def __init__(self, sent_id, num, expand):
        k = Sentence.objects.get(pk=sent_id)
        self.tagged = self.bold(k.tagged, num)
        self.id = sent_id
        self.doc_id = k.doc_id
        self.correct = k.correct
        self.expand = ''
        for i in range(sent_id-expand, sent_id):
            try:
                sent = Sentence.objects.get(pk=i)
                self.expand += sent.tagged + ' '
            except:
                pass
        self.expand += self.tagged + ' '
        for i in range(sent_id+1, sent_id+expand+1):
            try:
                sent = Sentence.objects.get(pk=i)
                self.expand += sent.tagged + ' '
            except:
                pass

    def bold(self, tagged, num):
        s = regSpans.findall(tagged)
        for i in num:
            try:
                s[i-1] = regToken.sub('"><b>\\1</b></span>', s[i-1])
            except:
                pass  #todo find the bug here
                # with codecs.open('s.txt', 'w', encoding='utf-8') as f:
                #     f.write(' '.join(str(ciph) for ciph in num))
                #     f.write('\r\n')
                #     f.write(tagged)
        return ' '.join(s)


def get_subcorpus(query):
    req = 'SELECT id FROM `annotator_document` WHERE 1 '
    if u'rulec' in query:
        req += 'AND subcorpus="RULEC" '
    mode = query.get(u'mode').encode('utf-8')
    if mode != u'any':
        req += 'AND mode="'+ mode +'" '
    background = query.get(u'background').encode('utf-8')
    if background != u'any':
        req += 'AND language_background="'+ background +'" '
    gender = query.get(u'gender').encode('utf-8')
    if gender != u'any':
        req += 'AND gender="'+ gender +'" '
    date1 = query.get(u'date1')
    if date1 != u'':
        req += 'AND date1>='+ date1.encode('utf-8') +' '
    date2 = query.get(u'date2')
    if date2 != u'':
        req += 'AND date2<='+ date2.encode('utf-8') +' '
    language = query.getlist(u'language[]')
    if language != []:
        one = []
        for lang in language:
            one.append('native="'+ lang.encode('utf-8') +'"')
        if len(one) == 1:
            req += 'AND '+ one[0]
        else:
            req += 'AND (' + ' OR '.join(one) + ')'
    # with codecs.open('s.txt', 'w', encoding='utf-8') as f:
    #     f.write(req)
    db = Database()
    docs = [str(i[0]) for i in db.execute(req)]
    subsum = db.execute('SELECT SUM(sentences), SUM(words) FROM `annotator_document` WHERE id IN (' +req + ')')
    flag = False if req == 'SELECT id FROM `annotator_document` WHERE 1 ' else True
    return docs, subsum[0][0], subsum[0][1], flag


def pages(sent_list, page, num):
    paginator = Paginator(sent_list, num)
    try:
        sents = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        sents = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        sents = paginator.page(paginator.num_pages)
    return sents

def exact_search(word, docs, flag, expand):
    db = Database()
    # db.cur.execute('SELECT tok.sent_id, tok.doc_id, sent.text FROM `annotator_token` tok, `annotator_sentence` sent WHERE tok.token="дом" and tok.sent_id=sent.id;')
    req1 = 'SELECT COUNT(DISTINCT doc_id) FROM `annotator_token` WHERE token="'+word + '" '
    if flag:
        req1 += 'AND doc_id IN ('+','.join(docs) + ');'
    docs_len = int(db.execute(req1)[0][0])
    req2 = 'SELECT sent_id, num FROM `annotator_token` WHERE token="'+ word +'" '
    if flag:
        req2 += 'AND doc_id IN ('+','.join(docs) + ');'
    tokens = db.execute(req2)
    # tokens = Token.objects.filter(token__exact=word)
    e = defaultdict(list)
    for i, j in tokens:
        e[i].append(j)
    jq = []
    sent_list = [ShowSentence(i, e[i], expand) for i in e]
    for sent in sent_list:
        # sent.temp = bold(word, sent.tagged)
        # sent.save()
        jq.append(jquery.replace('***', str(sent.id)))
    return jq, sent_list, word, docs_len

def lex_search(query, docs, flag, expand):
    # print query
    words = query.getlist(u'wordform[]')
    lexis = query.getlist(u'lex[]')
    grams = query.getlist(u'grammar[]')
    errs = query.getlist(u'errors[]')
    # print query.getlist(u'major'), query.getlist(u'genre')
    # froms = query.getlist(u'from[]')
    # tos = query.getlist(u'to[]')
    # <QueryDict: u'wordform[]' u'date1':  u'grammar[]': [u'S', u'A'], [u''], u'format': [u'full'], u'errors[]': u'from[]' u'major':  u'sort_by': [u'wordform'], u'additional[]': u'gender' u'genre'  u'per_page': [u'10'], u'expand': [u'+-1'], u'to[]'}>
    sent_list = {}
    jq = []
    # for wn in xrange(len(words)):
    wn = 0
    word = words[wn].lower().encode('utf-8')
    lex = lexis[wn].encode('utf-8')
    gram = grams[wn].encode('utf-8')
    err = errs[wn].encode('utf-8')
    rows = collect_data([word, lex, gram, err, docs, flag])
    e = defaultdict(list)
    if rows:
        if len(rows[0]) == 2:
            for i, j in rows:
                e[i].append(j)
        else:
            for i, j, k in rows:
                for n in range(j, k+1):
                    e[i].append(n)
    sent_list = [ShowSentence(i, e[i], expand) for i in e]
    for sent in sent_list:
        jq.append(jquery.replace('***', str(sent.id)))
    word=' '.join(query.getlist(u'wordform[]'))
    return jq, sent_list, word, len(set([s.doc_id for s in sent_list]))


def collect_data(arr):
    word, lex, gram, err, docs, flag = arr
    if all(i=="" for i in [word, lex, gram, err]):
        return []
    if [word, lex, gram] == ["", "", ""] and err != '':
        req = '''SELECT DISTINCT document_id, start, end FROM annotator_annotation
                 LEFT JOIN annotator_sentence
                 ON annotator_annotation.document_id = annotator_sentence.id WHERE 1 '''
        errs = [i for i in re.split(':?,|\\||\\(|\\)', err.lower()) if i != '']
        for er in errs:
            req += 'AND tag REGEXP "[[:<:]]' + er + '[[:>:]]" '
        if flag:
            req += 'AND doc_id_id IN ('+','.join(docs)+');'
    else:
        if err != '':
            req = '''SELECT DISTINCT sent_id, num FROM  annotator_token
        LEFT JOIN annotator_morphology
        ON annotator_token.id = annotator_morphology.token_id
        LEFT JOIN annotator_annotation
        ON annotator_token.sent_id = annotator_annotation.document_id
        WHERE 1 '''
            errs = [i for i in re.split(':?,|\\||\\(|\\)', err.lower()) if i != '']
            for er in errs:
                req += 'AND tag LIKE "%' + er + '%" '
            req += 'AND num>= annotator_annotation.start AND num <= annotator_annotation.end '
        else:
            req = '''SELECT DISTINCT sent_id, num FROM  annotator_token
        LEFT JOIN annotator_morphology
        ON annotator_token.id = annotator_morphology.token_id
        WHERE 1 '''
        if word != '':
            req += 'AND lem="'+word+'" '
        if lex != '':
            req += 'AND lex LIKE "%' + lex + '%" '
        if gram != '':
            req += parse_gram(gram)
        if flag:
            req += 'AND doc_id IN ('+','.join(docs)+');'
    # f = codecs.open('s.txt', 'w')
    # f.write(req)
    # f.close()
    db = Database()
    rows = db.execute(req)
    return rows

def parse_gram(gram):
    req = ''
    arr = gram.split(',')
    for gr in arr:
        one = ['gram REGEXP "[[:<:]]' + i + '[[:>:]]"' for i in gr.replace(')', '').replace('(', '').split('|')]
        if len(one) == 1:
            req += 'AND '+ one[0] + ' '
        else:
            req += 'AND (' + ' OR '.join(one) + ') '
    return req