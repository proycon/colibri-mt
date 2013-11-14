#!/usr/bin/env python3

from __future__ import print_function, unicode_literals, division, absolute_import
import colibricore
import os
import sys
import numpy
import argparse
import colibrimt.alignmentmodel


def extractskipgrams(alignmodel, maxlength= 8, minskiptypes=2, tmpdir="./", quiet=False):
    if not quiet: print("Extracting temporary source patterns",file=sys.stderr)
    sourcepatternfile = tmpdir + "/sourcepatterns.colibri.dat"
    with open(sourcepatternfile,'wb') as f:
        for sourcepattern in alignmodel.sourcepatterns():
            f.write(bytes(sourcepattern) + '\0')


    if not quiet: print("Extracting temporary target patterns",file=sys.stderr)
    targetpatternfile = tmpdir + "/targetpatterns.colibri.dat"
    with open(targetpatternfile,'wb') as f:
        for targetpattern in alignmodel.targetpatterns():
            f.write(bytes(targetpattern) + '\0')


    options = colibricore.PatternModelOptions()
    options.MINTOKENS = 1
    options.MINSKIPTYPES = minskiptypes
    options.MAXLENGTH = maxlength
    options.DOSKIPGRAMS = True


    #we first build skipgrams from the patterns found in the phrase-table, for both sides independently,
    #using indexed pattern models

    if not quiet: print("Building source pattern model",file=sys.stderr)
    sourcemodel = colibricore.IndexedPatternModel()
    sourcemodel.train(sourcepatternfile,options)

    if not quiet: print("Building target pattern model",file=sys.stderr)
    targetmodel = colibricore.IndexedPatternModel()
    targetmodel.train(targetpatternfile,options)

    #then for each pair in the phrasetable, we see if we can find abstracted pairs

    for i, sourcepattern, targetpattern, features in enumerate(alignmodel.items()):
        assert(isinstance(features[-1], list))

        if sourcepattern in sourcemodel and targetpattern in targetmodel:
            #find abstractions
            sourcetemplates = []
            targettemplates = []

            for template in sourcemodel.gettemplates(sourcepattern):
                if template.isskipgram() and sourcemodel[template] >= mintokens:
                    sourcetemplates.append(template)

            for template in targetmodel.gettemplates(targetpattern):
                if template.isskipgram() and targetmodel[template] >= mintokens:
                    targettemplates.append(template)

            #these will act as a memory buffer, saving time
            sourceinstances = {}
            targetinstances = {}

            for sourcetemplate in sourcetemplates:
                for targettemplate in targettemplates:
                    if not alignmodel.haspair(sourcetemplate, targettemplate): #each pair needs to be processed only once
                        #we now have two skipgrams, to be proper alignments their gaps must only align with gaps:

                        validalignment=False
                        for sourceindex, targetindex in features[-1]:
                            validalignment = (sourcetemplate.isgap(sourceindex) == targettemplate.isgap(targetindex))
                            if not validalignment: break
                        if not validalignment: continue

                        #if we made it here we have a proper pair!

                        alignmodel[(sourcetemplate,targettemplate)] = [1,0,1,0,features[-2],features[-1]] #lexical probability disabled (0),


                        #Now we have to compute a new score vector based on the score vectors of the possible instantiations
                        #find all instantiations
                        #if not sourcetemplate in sourceinstances: #only once per sourcetemplate
                        #    sourceinstances[sourcetemplate] = sourcemodel.getinstantiations(sourcetemplate)
                        #if not targettemplate in targetinstances: #only once per sourcetemplate
                        #    targetinstances[targettemplate] = targetmodel.getinstantiations(targettemplate)


                        #usedsources = colibricore.PatternSet()
                        #usedtargets = colibricore.PatternSet()
                        #scorepart_t = numpy.zeros(2)
                        #scorepart_s = numpy.zeros(2)
                        #total_s = 0
                        #total_t = 0
                        #for sourceinst in sourceinstances[sourcetemplate]:
                        #    for targetinst in targetinstances[sourcetemplate]:
                        #        if alignmodel.haspair(sourceinst, targetinst):
                        #            usedsources.add(sourceinst)
                        #            instfeatures = alignmodel[(sourceinst,targetinst)]

                        #            #we will assume a standard moses configuration of features
                        #            assert(len(instfeatures) == 6)
                        #            #1,2 : p(s|t)   3,4 : p(t|s)    4: word penalty , 5: word alignments (not used here)

                        #            total_t[0] += instfeatures[0]
                        #            scorepart_t[1] += instfeatures[1]
                        #            scorepart_s[0] += instfeatures[3]
                        #            scorepart_s[1] += instfeatures[4]

    del sourcemodel
    del targetmodel

    #now we are going to renormalise the scores (leave lexical weights intact)
    alignmodel.normalize('s-t-')


    os.unlink(sourcepatternfile)
    os.unlink(targetpatternfile)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Extract skipgrams from a Moses phrasetable", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-t','--minskiptypes', type=int,help="Minimal skip types", action='store',default=2,required=False)
    parser.add_argument('-i','--input',type=str,help="Input phrase table", action='store',required=True)
    parser.add_argument('-l','--maxlength',type=int,help="Maximum length", action='store',default=8,required=False)
    parser.add_argument('-T','--tmpdir',type=str,help="Temporary work directory", action='store',default="./",required=Fale)
    args = parser.parse_args()
    #args.storeconst, args.dataset, args.num, args.bar

    extractskipgrams(alignmodel, args.maxlength, args.minskiptypes, args.tmpdir)


if __name__ == '__main__':
    main()
