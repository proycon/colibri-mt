#!/usr/bin/env python3

from __future__ import print_function, unicode_literals, division, absolute_import

import sys
import datetime
import bz2
import gzip
import colibricore
import argparse
import pickle
import os


class AlignmentModel:
    def __init__(self, multivalue=True, singleintvalue=False):
        self.values = {}
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
                self.alignedpatterns[(sourcepattern,targetpattern)] = valueid
                self.values[valueid] = [value]
            else:
                self.alignedpatterns[(sourcepattern,targetpattern)] = valueid
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


    def targetpatterns(self, sourcepattern=None):
        if sourcepattern is None:
            s = colibricore.PatternSet()
            for sourcepattern in self.alignedpatterns:
                for targetpattern in self.alignedpatterns.children(sourcepattern):
                    s.add(targetpattern)

            for targetpattern in s:
                yield targetpattern
        else:
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
        print( "Loaded keys: alignments for " + str(len(self.alignedpatterns)) + " source patterns",file=sys.stderr)
        if os.path.exists(fileprefix + ".colibri.alignmodel-values"):
            self.singleintvalue= False
            with open(fileprefix + ".colibri.alignmodel-values",'rb') as f:
                self.values = pickle.load(f)
            #check if we are multivalued
            for key, value in self.values.items():
                self.multivalue = (isinstance(value, tuple) or isinstance(value, list))
                break
            print( "Loaded values (" + str(len(self.values)) + ")",file=sys.stderr)
        else:
            self.singleintvalue= True

    def save(self, fileprefix):
        """Output"""
        self.alignedpatterns.write(fileprefix + ".colibri.alignmodel-keys")
        if not self.singleintvalue:
            with open(fileprefix + ".colibri.alignmodel-values",'wb') as f:
                pickle.dump(self.values, f)

    def output(self, sourcedecoder, targetdecoder):
        for sourcepattern, targetpattern, value in self.items():
            print(sourcepattern.tostring(sourcedecoder) + "\t" ,end="")
            print(targetpattern.tostring(targetdecoder) + "\t" ,end="")
            if not self.multivalue or self.singleintvalue:
                print(str(value))
            else:
                for v in value:
                    print(str(v) + "\t" ,end="")
            print()



    def sourcemodel(self):
        model = colibricore.UnindexedPatternModel()
        for sourcepattern in self.sourcepatterns():
            model[sourcepattern] = model[sourcepattern] + 1
        return model

    def targetmodel(self):
        model = colibricore.UnindexedPatternModel()
        for targetpattern in self.targetpatterns():
            model[targetpattern] = model[targetpattern] + 1
        return model

    def _normaux(self, sourcepattern, targetpattern, total_s, total_t, value, index, sumover):
        if sumover == 's':
            total_s[sourcepattern] += value[index]
        elif sumover == 't':
            total_t[targetpattern] += value[index]
        else:
            raise Exception("sumover can't be " + sumover)

    def normalize(self, sumover='s'):
        if self.singleintvalue:
            raise Exception("Can't normalize AlignedPatternDict with singleintvalue set")
        total_s = colibricore.PatternDict_float()
        total_t = colibricore.PatternDict_float()

        for sourcepattern, targetpattern, value in self:
            if self.multivalue:
                for i in range(0, max(len(value), len(sumover))):
                    if sumover[i] == 's':
                        total_s[targetpattern] += value[i]
                    elif sumover[i] == 't':
                        total_t[sourcepattern] += value[i]
            else:
                if sumover == 's':
                    total_s[targetpattern] += value
                elif sumover[i] == 't':
                    total_t[sourcepattern] += value


        for sourcepattern, targetpattern, value in self:
            if self.multivalue:
                 for i in range(0,len(len(value),len(sumover))):
                    if sumover[i] == 's':
                        try:
                            value[i] = value[i] / total_s[targetpattern]
                        except ZeroDivisionError: #ok, just leave unchanged
                            pass
                    elif sumover[i] == 't':
                        try:
                            value[i] = value[i] / total_t[sourcepattern]
                        except ZeroDivisionError: #ok, just leave unchanged
                            pass
                    elif sumover[i] == '0':
                        value[i] = 0
                    elif sumover[i] == '-':
                        pass
            else:
                if sumover == 's':
                    self.values[self.alignedpatterns[(sourcepattern,targetpattern)]] = value / total_s[targetpattern]
                elif sumover == 't':
                    self.values[self.alignedpatterns[(sourcepattern,targetpattern)]] = value / total_t[sourcepattern]
                elif sumover == '0':
                    self.values[self.alignedpatterns[(sourcepattern,targetpattern)]] = 0
                elif sumover == '-':
                    pass


class FeatureConfiguration:
    def __init__(self):
        self.conf = []
        self.decoders = {}

    def addfactorfeature(self, classdecoder, leftcontext=0, focus=True,rightcontext=0):
        if isinstance(classdecoder, colibricore.ClassDecoder):
            self.decoders[classdecoder.filename] = classdecoder
            classdecoder = classdecoder.filename
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


    def loaddecoders(self, *args):
        for item in self:
            if item[0] == colibricore.Pattern:
                decoderfile = item[1]
                if decoderfile not in self.decoders:
                    foundinargs = False
                    for x in args:
                        if x.filename == decoderfile:
                            self.decoders[x.filename] = x
                    if not foundinargs:
                        self.decoders[decoderfile] = colibricore.ClassDecoder(decoderfile)


class FeaturedAlignmentModel(AlignmentModel):
    def __init__(self, conf=FeatureConfiguration()):
        assert isinstance(conf, FeatureConfiguration)
        self.conf = conf
        super().__init__(True,False)


    def load(self, fileprefix):
        if os.path.exists(fileprefix + ".colibri.alignmodel-featconf"):
            with open(fileprefix + ".colibri.alignmodel-featconf",'rb') as f:
                self.conf.conf = pickle.load(f)
        super().load(fileprefix)

    def save(self, fileprefix):
        with open(fileprefix + ".colibri.alignmodel-featconf",'wb') as f:
            pickle.dump(self.conf.conf, f)
        super().save(fileprefix)

    def __iter__(self):
        for sourcepattern, targetpattern, valueid in self.alignedpatterns.items():
            for featurevector in self.values[valueid]: #multiple feature vectors per alignment possible
                yield sourcepattern, targetpattern, featurevector

    def output(self, sourcedecoder, targetdecoder, *preloadeddecoders):
        preloadeddecoders = (sourcedecoder, targetdecoder) +  preloadeddecoders
        self.conf.loaddecoders(*preloadeddecoders)

        print("Configuration:",len(self.conf),file=sys.stderr)


        for sourcepattern, targetpattern, features in self.items():
            print(sourcepattern.tostring(sourcedecoder) + "\t" ,end="")
            print(targetpattern.tostring(targetdecoder) + "\t" ,end="")
            it = iter(features)
            for i, conf in enumerate(self.conf):
                if conf[0] == colibricore.Pattern:
                    _, classdecoder, leftcontext, dofocus, rightcontext = conf
                    classdecoder = self.conf.decoders[classdecoder]
                    n = leftcontext + rightcontext
                    if dofocus: n += 1
                    for j in range(0,n):
                        p = next(it)
                        print(p.tostring(classdecoder) ,end="")
                        if i < len(self.conf) -1:
                            #not the last feature yet:
                            print("\t",end="")
                else:
                    print(str(next(it)) + "\t" ,end="")
            print()

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

        haswordalignments = False

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
                scores = [ float(x) for x in segments[score_column-1].strip().split()  ]
            else:
                scores = []


            #if align2_column > 0:
            #    try:
            #        null_alignments = segments[align2_column].count("()")
            #    except:
            #        null_alignments = 0
            #else:
            #    null_alignments = 0

            if scorefilter:
                if not scorefilter(scores): continue

            if len(segments) >= 4:
                scores.append( [ tuple(x.split('-')) for x in segments[3].split() ] )
                haswordalignments = True
            elif haswordalignments:
                scores.append([])


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
        if haswordalignments:
            self.conf.addfeature(list)

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




def mosesphrasetable2alignmodel(inputfilename,sourceclassfile, targetclassfile, outfileprefix, quiet=False):
    if not quiet: print("Reading source encoder " + sourceclassfile,file=sys.stderr)
    sourceencoder = colibricore.ClassEncoder(sourceclassfile)
    if not quiet: print("Reading target encoder " + targetclassfile,file=sys.stderr)
    targetencoder = colibricore.ClassEncoder(targetclassfile)
    if not quiet: print("Initialising featured alignment model",file=sys.stderr)
    model = FeaturedAlignmentModel()
    if not quiet: print("Loading moses phrasetable",file=sys.stderr)
    model.loadmosesphrasetable(inputfilename, sourceencoder, targetencoder)
    if not quiet: print("Loaded " + str(len(model)) + " source patterns")
    if not quiet: print("Saving alignment model",file=sys.stderr)
    model.save(outfileprefix)


def main_mosesphrasetable2alignmodel():
    try:
        inputfilename,sourceclassfile, targetclassfile,outfileprefix = sys.argv[1:]
    except:
        print("mosesphrasetable2alignmodel inputfilename sourceclassfile targetclassfile outfileprefix",file=sys.stderr)
        return 1

    mosesphrasetable2alignmodel(inputfilename, sourceclassfile, targetclassfile, outfileprefix)


def main_alignmodel():
    parser = argparse.ArgumentParser(description="Load and view the specified aligment model", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-i','--inputfile',type=str,help="Input alignment model (file prefix without .colibri.alignmodel-* extension)", action='store',required=True)
    parser.add_argument('-S','--sourceclassfile',type=str,help="Source class file", action='store',required=True)
    parser.add_argument('-T','--targetclassfile',type=str,help="Target class file", action='store',required=True)
    args = parser.parse_args()
    #args.storeconst, args.dataset, args.num, args.bar


    print("Loading source decoder " + args.sourceclassfile,file=sys.stderr)
    sourcedecoder = colibricore.ClassDecoder(args.sourceclassfile)
    print("Loading target decoder " + args.targetclassfile,file=sys.stderr)
    targetdecoder = colibricore.ClassDecoder(args.targetclassfile)
    print("Loading alignment model",file=sys.stderr)
    if os.path.exists(args.inputfile + ".colibri.alignmodel-featconf"):
        model = FeaturedAlignmentModel()
        featured = True
    else:
        model = AlignmentModel()
        featured = False
    model.load(args.inputfile)
    print("Outputting",file=sys.stderr)
    model.output(sourcedecoder,targetdecoder)




