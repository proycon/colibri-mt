#!/usr/bin/env python3

from __future__ import print_function, unicode_literals, division, absolute_import

import sys
import datetime
import bz2
import gzip
import colibricore
import timbl
import argparse
import pickle


class AlignmentModel:
    def __init__(self, multivalue=True, singleintvalue=False):
        self.values = []
        self.newvalueid = 0
        self.alignedpatterns = colibricore.AlignedPatternDict_int32()
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

    def sourcepatterns(self):
        for sourcepattern in self.alignedpatterns:
            yield sourcepattern


    def targetpatterns(self, sourcepattern):
        for targetpattern in self.alignedpatterns.children(sourcepattern):
            yield targetpattern

    def items(self):
        return iter(self)

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


    def __contains__(self, item):
        return item in self.alignedpatterns


    def load(self, fileprefix):
        self.alignedpatterns.read(fileprefix + ".colibri.alignmodel-keys")
        self.values = pickle.load(fileprefix + ".colibri.alignmodel-values")

    def save(self, fileprefix):
        """Output"""
        self.alignedpatterns.write(fileprefix + ".colibri.alignmodel-keys")
        pickle.dump(self.values, fileprefix + ".colibri.alignmodel-values")


class FeatureConfiguration:
    def __init__(self):
        self.conf = []

    def addfactorfeature(self, classdecoder, leftcontext=0, focus=True,rightcontext=0):
        self.conf.append( ( colibricore.Pattern, classdecoder, leftcontext, focus, rightcontext) )

    def addfeature(self, type):
        """Will not be propagated to Moses phrasetable"""
        self.conf.append( ( type,False) )

    def addscorefeature(self, type):
        """Will be propagated to Moses phrasetable"""
        self.conf.append( ( type,True) )

    def __len__(self):
        return len(self.conf)

    def __iter__(self):
        for x in self.conf:
            yield x

    def __getitem__(self, index):
        return self.conf[index]


class FeaturedAlignmentModel(AlignmentModel):
    def __init__(self, conf=FeatureConfiguration()):
        assert isinstance(conf, FeatureConfiguration)
        self.conf = conf
        super().__init__(True,False)


    def savemosesphrasetable(self, filename, sourcedecoder, targetdecoder):
        """Output for moses"""
        with open(filename,'w',encoding='utf-8') as f:
            for sourcepattern, targetpattern, features in self:
                f.write(sourcepattern.tostring(sourcedecoder) + " ||| " + targetpattern.tostring(targetdecoder) + " ||| ")
                for i, feature, featureconf in enumerate(zip(features, self.conf)):
                    if featureconf[0] != colibricore.Pattern and featureconf[1]:
                        if (i > 0): f.write(" ")
                        f.write(str(feature))
                f.write("\n")

    def loadmosesphrasetable(self, filename, sourceencoder, targetencoder, quiet=False, reverse=False, delimiter="|||", score_column = 3, max_sourcen = 0, scorefilter = lambda x:True):
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

        self.conf = FeatureConfiguration()
        for x in scores:
            self.conf.addscorefeature(float)

    def patternswithindexes(self, sourcemodel, targetmodel):
        """Finds occurrences (positions in the source and target models) for all patterns"""
        for sourcepattern in self.sourcepatterns():
            if not sourcepattern in sourcemodel:
                print("Warning: a pattern from the phrase table was not found in the source model (pruned for not meeting a threshold most likely)" ,file=sys.stderr)
                continue
            sourceindexes = sourcemodel[sourcepattern]
            for targetpattern in self.targetpatterns(sourcepattern):
                if not targetpattern in targetmodel:
                    print("Warning: a pattern from the phrase table was not found in the target model (pruned for not meeting a threshold most likely)" ,file=sys.stderr)
                    continue
                targetindexes = targetmodel[targetpattern]

                #for every occurrence of this pattern in the source
                for sentence, token in sourceindexes:
                    #is a target pattern found in the same sentence? (if so we *assume* they're aligned, we don't actually use the word alignments anymore here)
                    targetmatch = False
                    for targetsentence,targettoken in targetindexes:
                        if sentence == targetsentence:
                            yield sourcepattern, targetpattern, sentence, token, targetsentence, targettoken
                            targetmatch = True
                            break


    def extractfactorfeatures(self, sourcemodel, targetmodel, factoredcorpora):
        featurevector = []
        assert isinstance(sourcemodel, colibricore.IndexedPatternModel)
        assert isinstance(targetmodel, colibricore.IndexedPatternModel)

        factorconf = [x for x in self.conf if x[0] == colibricore.Pattern ]
        if len(factoredcorpora) != len(factorconf):
            raise ValueError("Expected " + str(len(factorconf)) + " instances in factoredcorpora, got " + str(len(factoredcorpora)))

        if not all([ isinstance(x,colibricore.IndexedCorpus) for x in factoredcorpora]):
            raise ValueError("factoredcorpora elements must be instances of IndexedCorpus")


        for sourcepattern, targetpattern, sentence, token,_,_ in self.patternswithindexes(sourcemodel, targetmodel):
            n = len(sourcepattern)
            featurevector= []
            for factoredcorpus, factor in zip(factoredcorpora, factorconf):
                _,classdecoder, leftcontext, focus, rightcontext = factor
                sentencelength = factoredcorpus.sentencelength(sentence)
                for i in range(token - leftcontext,token):
                    if token < 0:
                        unigram = colibricore.beginpattern
                    else:
                        unigram = factoredcorpus[(sentence,i)]
                    featurevector.append(unigram)
                if focus:
                    featurevector.append(factoredcorpus[(sentence,token):(sentence,token+n)])
                for i in range(token + n , token + n + rightcontext):
                    if token > sentencelength:
                        unigram = colibricore.endpattern
                    else:
                        unigram = factoredcorpus[(sentence,i)]
                    featurevector.append(unigram)
            yield sentence, token, sourcepattern, targetpattern, featurevector





def mosesphrasetable2alignmodel(inputfilename,sourceclassfile, targetclassfile, outfileprefix):
    sourceencoder = colibricore.ClassEncoder(sourceclassfile)
    targetencoder = colibricore.ClassEncoder(sourceclassfile)
    model = FeaturedAlignmentModel()
    m.loadmosesphrasetable(inputfilename, sourceencoder, targetencoder)
    m.save(outfileprefix)

def main_mosesphrasetable2alignmodel():
    try:
        inputfilename,sourceclassfile, targetclassfile,outfileprefix = sys.argv[1:]
    except:
        print("mosesphrasetable2alignmodel inputfilename sourceclassfile targetclassfile outfileprefix",file=sys.stderr)
        return 1

    mosesphrasetable2alignmodel(inputfilename, sourceclassfile, targetclassfile, outfileprefix)




