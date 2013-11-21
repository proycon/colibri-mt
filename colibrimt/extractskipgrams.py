#!/usr/bin/env python3

from __future__ import print_function, unicode_literals, division, absolute_import
import colibricore
import os
import sys
import numpy
import argparse

from copy import copy
from colibrimt.alignmentmodel import FeaturedAlignmentModel


def extractskipgrams(alignmodel, maxlength= 8, minskiptypes=2, tmpdir="./", constrainsourcemodel = None, constraintargetmodel = None, quiet=False,debug=False):
    if not quiet: print("Writing all source patterns to temporary file",file=sys.stderr)
    sourcepatternfile = tmpdir + "/sourcepatterns.colibri.dat"
    with open(sourcepatternfile,'wb') as f:
        for sourcepattern in alignmodel.sourcepatterns():
            if not constrainsourcemodel or sourcepattern in constrainsourcemodel:
                f.write(bytes(sourcepattern) + b'\0')


    if not quiet: print("Writing all target patterns to temporary file",file=sys.stderr)
    targetpatternfile = tmpdir + "/targetpatterns.colibri.dat"
    with open(targetpatternfile,'wb') as f:
        for targetpattern in alignmodel.targetpatterns():
            if not constraintargetmodel or targetpattern in constraintargetmodel:
                f.write(bytes(targetpattern) + b'\0')


    options = colibricore.PatternModelOptions()
    options.MINTOKENS = 1
    options.MINSKIPTYPES = minskiptypes
    options.MAXLENGTH = maxlength
    options.DOSKIPGRAMS = True


    #we first build skipgrams from the patterns found in the phrase-table, for both sides independently,
    #using indexed pattern models

    if not quiet: print("Building source pattern model",file=sys.stderr)
    sourcemodel = colibricore.IndexedPatternModel()
    sourcemodel.train(sourcepatternfile,options, constrainsourcemodel)

    if not quiet: print("Building target pattern model",file=sys.stderr)
    targetmodel = colibricore.IndexedPatternModel()
    targetmodel.train(targetpatternfile,options, constraintargetmodel)

    #then for each pair in the phrasetable, we see if we can find abstracted pairs
    found = 0

    skipped = 0

    if not quiet: print("Computing total count",file=sys.stderr)
    total = alignmodel.itemcount()


    if not quiet: print("Finding abstracted pairs",file=sys.stderr)
    for i, (sourcepattern, targetpattern, features) in enumerate(alignmodel.items()):
        if not isinstance(features, list) and not isinstance(features, tuple):
            print("WARNING: Expected feature vector, got " + str(type(features)),file=sys.stderr)
            continue
        if not isinstance(features[-1], list) and not isinstance(features[-1], tuple):
            print("WARNING: Word alignments missing for a pair, skipping....",file=sys.stderr)
            continue

        if not quiet and (i+1) % 100 == 0: print("@"+str(i)+"/"+str(total)+" = " + str(round((i/total) * 100,2)) + '%' + ",  found " + str(found) + " skipgram pairs thus-far, skipped " + str(skipped),file=sys.stderr)


        if sourcepattern in sourcemodel and targetpattern in targetmodel:
            #find abstractions
            if debug: print("\tFinding abstractions for sourcepattern ", sourcepattern.tostring(debug[0]) + " with targetpattern " + targetpattern.tostring(debug[1]),file=sys.stderr)
            sourcetemplates = []
            targettemplates = []

            for template, count in sourcemodel.gettemplates(sourcepattern):
                if template.isskipgram() and template in sourcemodel:
                    sourcetemplates.append(template)
                    if debug: print("\t\tAdded source template ", template.tostring(debug[0]),file=sys.stderr)

            for template, count in targetmodel.gettemplates(targetpattern):
                if template.isskipgram() and template in targetmodel:
                    targettemplates.append(template)
                    if debug: print("\t\tAdded source template ", template.tostring(debug[1]),file=sys.stderr)

            #these will act as a memory buffer, saving time
            sourceinstances = {}
            targetinstances = {}

            for sourcetemplate in sourcetemplates:
                for targettemplate in targettemplates:
                    if not alignmodel.haspair(sourcetemplate, targettemplate): #each pair needs to be processed only once
                        #we now have two skipgrams, to be proper alignments their gaps must only align with gaps:


                        if debug: print("\t\tProcessing skipgram pair ", sourcetemplate.tostring(debug[0]) + " -- " + targettemplate.tostring(debug[1]),file=sys.stderr)

                        validalignment=False
                        for sourceindex, targetindex in features[-1]:
                            validalignment = (sourcetemplate.isgap(sourceindex) == targettemplate.isgap(targetindex))
                            if not validalignment: break
                        if not validalignment: continue

                        if debug: print("\t\tAlignment valid! Adding!",file=sys.stderr)

                        #if we made it here we have a proper pair!

                        alignmodel.add(sourcetemplate,targettemplate, [1.0,0.0,1.0,0.0,features[-2],copy(features[-1])]  ) #lexical probability disabled (0),
                        found += 1

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
        else:
            skipped += 1

    print("Unloading models",file=sys.stderr)
    del sourcemodel
    del targetmodel


    #now we are going to renormalise the scores (leave lexical weights intact as is)
    print("Renormalising alignment model",file=sys.stderr)
    alignmodel.normalize('s-t-')


    print("Cleanup",file=sys.stderr)
    os.unlink(sourcepatternfile)
    os.unlink(targetpatternfile)

    return alignmodel

def main():
    parser = argparse.ArgumentParser(description="Extract skipgrams from a Moses phrasetable", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-t','--minskiptypes', type=int,help="Minimal skip types", action='store',default=2,required=False)
    parser.add_argument('-i','--inputfile',type=str,help="Input alignment model (file prefix without .colibri.alignmodel-* extension) or moses phrasetable ", action='store',required=True)
    parser.add_argument('-o','--outputfile',type=str,help="Output alignment model (file prefix without .colibri.alignmodel-* extension). Same as input if not specified!", default="", action='store',required=False)
    parser.add_argument('-l','--maxlength',type=int,help="Maximum length", action='store',default=8,required=False)
    parser.add_argument('-W','--tmpdir',type=str,help="Temporary work directory", action='store',default="./",required=False)
    parser.add_argument('-S','--sourceclassfile',type=str,help="Source class file", action='store',required=True)
    parser.add_argument('-T','--targetclassfile',type=str,help="Target class file", action='store',required=True)
    parser.add_argument('-m','--constrainsourcemodel',type=str,help="Source patternmodel, used to constrain possible patterns", action='store',required=False)
    parser.add_argument('-M','--constraintargetmodel',type=str,help="Target patternmodel, used to constrain possible patterns", action='store',required=False)
    parser.add_argument('-D','--debug',help="Enable debug mode", action='store_true',required=False)
    args = parser.parse_args()
    #args.storeconst, args.dataset, args.num, args.bar

    if args.constrainsourcemodel:
        print("Loadin source model for constraints",file=sys.stderr)
        constrainsourcemodel = colibricore.UnindexedPatternModel(args.constrainsourcemodel)
    else:
        constrainsourcemodel = None

    if args.constraintargetmodel:
        print("Loading target model for constraints",file=sys.stderr)
        constraintargetmodel = colibricore.UnindexedPatternModel(args.constraintargetmodel)
    else:
        constraintargetmodel = None


    alignmodel = FeaturedAlignmentModel()
    if os.path.exists(args.inputfile + '.colibri.alignmodel-keys'):
        print("Loading colibri alignment model",file=sys.stderr)
        alignmodel.load(args.inputfile)
    else:
        print("Loading class encoders",file=sys.stderr)
        sourceencoder = colibricore.ClassEncoder(args.sourceclassfile)
        targetencoder = colibricore.ClassEncoder(args.targetclassfile)
        print("Loading moses phrase table",file=sys.stderr)
        alignmodel.loadmosesphrasetable(args.inputfile, sourceencoder, targetencoder)

    if args.debug:
        debug = (colibricore.ClassDecoder(args.sourceclassfile), colibricore.ClassDecoder(args.targetclassfile))
    else:
        debug = False


    extractskipgrams(alignmodel, args.maxlength, args.minskiptypes, args.tmpdir, constrainsourcemodel, constraintargetmodel,False, debug)

    if args.outputfile:
        outfile = args.outputfile
    else:
        outfile = os.path.basename(args.inputfile)
        if outfile[-3:] == '.gz': outfile = outfile[:-3]
        if outfile[-4:] == '.bz2': outfile = outfile[:-4]
        if outfile[-11:] == '.phrasetable': outfile = outfile[:-11]
        if outfile[-12:] == '.phrase-table': outfile = outfile[:-12]
    print("Saving alignment model to " + outfile,file=sys.stderr)
    alignmodel.save(outfile) #extensions will be added automatically


if __name__ == '__main__':
    main()
