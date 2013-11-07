#!/usr/bin/env python3

from __future__ import print_function, unicode_literals, division, absolute_import

import sys
import datetime
import bz2
import gzip
import colibricore
import timbl
import argparse



class AlignmentModel:
    def __init__(self, sourcedecoder, targetdecoder, multivalue=True, singleintvalue=False):
        self.values = []
        self.newvalueid = 0
        self.alignedpatterns = colibricore.AlignedPatternDict_int32()
        self.sourcedecoder = sourcedecoder
        self.targetdecoder = targetdecoder
        self.multivalue = multivalue
        self.singleintvalue = singleintvalue

    def add(self, sourcepattern, targetpattern, value):
        if not isinstance(sourcepattern, colibricore.Pattern):
            raise ValueError("Source pattern must be instance of Pattern")
        if not isinstance(targetpattern, colibricore.Pattern):
            raise ValueError("Target pattern must be instance of Pattern")

        if (sourcepattern, targetpattern) in self.alignedpatterns:
            valueid = self.alignedpatterns[(sourcepattern, targetpattern)]
            if self.singleintvalue:
                self.alignedpatterns[(sourcepattern,targetpattern)] = value
            elif self.multivalue:
                self.values[valueid].append(value)
            else:
                self.values[valueid] = value
        else:
            self.newvalueid += 1
            valueid = self.newvalueid
            if self.singleintvalue:
                self.alignedpatterns[(sourcepattern,targetpattern)] = value
            elif self.multivalue:
                self.values[valueid] = [value]
            else:
                self.values[valueid] = value

    def __len__(self):
        return len(self.alignedpatterns)

    def __iter__(self):
        if self.singleintvalue:
            for sourcepattern, targetpattern, value in self.alignedpatterns.items():
                yield sourcepattern, targetpattern, value
        else:
            for sourcepattern, targetpattern, valueid in self.alignedpatterns.items():
                yield sourcepattern, targetpattern, self.values[valueid]

    def __getitem__(self, item):
        if self.singleintvalue:
            return self.alignedpatterns[item]
        else:
            return self.values[self.alignedpatterns[item]]

    def __setitem__(self, item, value):
        if self.singleintvalue:
            self.alignedpatterns[item] = value
        else:
            self.values[self.alignedpatterns[item]] = value

    def load(self, filename, sourceencoder, targetencoder):
        with open(filename,'r',encoding='utf-8') as f:
            for line in f:
                fields = line.strip().split("\t")
                sourcepattern = sourceencoder.buildpattern(fields[0])
                targetpattern = targetencoder.buildpattern(fields[-1])
                for raw in fields[1:-1]:
                    type, value = raw.split('=',2)
                    features = []
                    if type == 's':
                        features.append(value)
                    elif type == 'p':
                        features.append(sourceencoder.buildpattern(value))
                    elif type == 'i':
                        features.append(int(value))
                    elif type == 'f':
                        features.append(float(value))
                    elif type == 'b':
                        features.append(bool(value))
                self.add(sourcepattern,features,targetpattern)

    def save(self, filename):
        """Output"""
        with open(filename,'w',encoding='utf-8') as f:
            for sourcepattern, features, targetpattern in self:
                f.write(sourcepattern.tostring(self.sourcedecoder))
                for feature in features:
                    f.write("\t")
                    if isinstance(feature,str):
                        f.write('s=' + feature)
                    elif isinstance(feature, colibricore.Pattern):
                        f.write('p=' + feature.tostring(self.sourcedecoder))
                    elif isinstance(feature,int):
                        f.write('i=' + str(feature))
                    elif isinstance(feature,float):
                        f.write('f=' + str(feature))
                    elif isinstance(feature,bool):
                        f.write('b=' + str(feature))
                    else:
                        raise TypeError
                f.write("\t" + targetpattern.tostring(self.targetdecoder)+"\n")


    def savemoses(self, filename):
        """Output for moses"""
        pass #TODO


    def loadmoses(self, filename, sourceencoder, targetencoder, quiet=False, reverse=False, delimiter="|||", score_column = 3, max_sourcen = 0, scorefilter = lambda x:True):
        """Load a phrase table from file into memory (memory intensive!)"""
        self.phrasetable = {}

        if filename.split(".")[-1] == "bz2":
            f = bz2.BZ2File(filename,'r')
        elif filename.split(".")[-1] == "gz":
            f = gzip.GzipFile(filename,'r')
        else:
            f = open(filename,'r',encoding='utf-8')
        linenum = 0
        prevsource = None
        targets = []

        while True:
            if not quiet:
                linenum += 1
                if (linenum % 100000) == 0:
                    print("Loading phrase-table: @" + str(linenum) + "\t(" + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ")",file=sys.stderr)
            line = f.readline()
            if not line:
                break

            #split into (trimmed) segments
            segments = [ segment.strip() for segment in line.split(delimiter) ]

            if len(segments) < 3:
                print("Invalid line: ", line, file=sys.stderr)
                continue

            #Do we have a score associated?
            if score_column > 0 and len(segments) >= score_column:
                scores = tuple( ( float(x) for x in segments[score_column-1].strip().split() ) )
            else:
                scores = tuple()

            #if align2_column > 0:
            #    try:
            #        null_alignments = segments[align2_column].count("()")
            #    except:
            #        null_alignments = 0
            #else:
            #    null_alignments = 0

            if scorefilter:
                if not scorefilter(scores): continue

            if reverse:
                if max_sourcen > 0 and segments[1].count(' ') + 1 > max_sourcen:
                    continue

                source = sourceencoder.buildpattern(segments[1]) #tuple(segments[1].split(" "))
                target = targetencoder.buildpattern(segments[0]) #tuple(segments[0].split(" "))
            else:
                if max_sourcen > 0 and segments[0].count(' ') + 1 > max_sourcen:
                    continue

                source = sourceencoder.buildpattern(segments[0]) #tuple(segments[0].split(" "))
                target = targetencoder.buildpattern(segments[1]) #tuple(segments[1].split(" "))


            self.add(source,target, scores)

        f.close()





    def extractfeatures(self, featureconf, sourcemodel, targetmodel, factoredcorpora):
        """Extracts features and adds it to the phrasetable"""

        #factoredcorpora is a list of IndexedCorpus instances, for each of the factors.. the base data is considered a factor like any other



        if len(factoredcorpora) != len(featureconf):
            raise ValueError("Expected " + str(len(featureconf)) + " instances in factoredcorpora, got " + str(len(factoredcorpora)))

        if not all([ isinstance(x,colibricore.IndexedCorpus) for x in factoredcorpora]):
            raise ValueError("factoredcorpora elements must be instances of IndexedCorpus")

        assert isinstance(sourcemodel, colibricore.IndexedPatternModel)
        assert isinstance(targetmodel, colibricore.IndexedPatternModel)

        for pattern in self.sourcepatterns:
            if not pattern in sourcemodel:
                print("Warning: a pattern from the phrase table was not found in the source model (pruned for not meeting a threshold most likely)" ,file=sys.stderr)
                continue


            sourceindexes = sourcemodel[pattern]

            for features, targetpattern in self[pattern]:
                if not targetpattern in targetmodel:
                    print("Warning: a pattern from the phrase table was not found in the target model (pruned for not meeting a threshold most likely)" ,file=sys.stderr)
                    continue

                targetindexes = targetmodel[targetpattern]

                #for every occurrence of this pattern in the source
                for sentence, token in sourceindexes:

                    #is a target pattern found in the same sentence? (if so we *assume* they're aligned, we don't actually use the word alignments anymore here)
                    targetmatch = False
                    for targetsentence,_ in targetindexes:
                        if sentence == targetsentence:
                            targetmatch = True
                            break
                    if not targetmatch:
                        continue

                    #good, we can start extracting features!!

                    #add the location to the features so we can find it later when we build intermediate location-based IDs instead of sourcepatterns
                    features.append(sentence)
                    features.append(token)

                    for factoredcorpus, factor in zip(factoredcorpora, featureconf.factors):
                        classdecoder, leftcontext, rightcontext = factor
                        features += _extractfeatures(pattern, sentence, token, factoredcorpus, leftcontext, rightcontext)





def _extractfeatures(pattern, sentence, token, factoredcorpus, leftcontext, rightcontext):
    featurevector = []
    n = len(pattern)
    sentencelength = factoredcorpus.sentencelength(sentence)
    for i in range(token - leftcontext,token):
        if token < 0:
            unigram = colibricore.BEGINPATTERN
        else:
            unigram = factoredcorpus[(sentence,i)]
        featurevector.append(unigram)
    for i in range(token + n , token + n + rightcontext):
        if token > sentencelength:
            unigram = colibricore.ENDPATTERN
        else:
            unigram = factoredcorpus[(sentence,i)]
        featurevector.append(unigram)
    return featurevector

class FeatureConfiguration:


    #the feature vectors will contain:
    #   the two-tuple (sentence, tokenoffset) of the beginning occurrence
    #   leftcontext from sourcepatternmodel
    #   rightcontext from sourcepatternmodel
    #   for each of the factors:
    #       leftcontext from factored indexedcorpus
    #        rightcontext from factored indexedcorpus


    def __init__(self, classdecoder, leftcontext, rightcontext):
        self.factors = []
        self.addfactor(  classdecoder, leftcontext, rightcontext )

    def addfactor(self,  classdecoder, leftcontext, rightcontext):
        self.data.append( ( classdecoder, leftcontext, rightcontext) )

    def __len__(self):
        return len(self.data)

