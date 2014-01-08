#!/usr/bin/env python3

from __future__ import print_function, unicode_literals, division, absolute_import

import argparse
import sys
import os
import subprocess
import datetime


def bold(s):
    CSI="\x1B["
    return CSI+"1m" + s + CSI + "0m"

def white(s):
    CSI="\x1B["
    return CSI+"37m" + s + CSI + "0m"


def red(s):
    CSI="\x1B["
    return CSI+"31m" + s + CSI + "0m"

def green(s):
    CSI="\x1B["
    return CSI+"32m" + s + CSI + "0m"


def yellow(s):
    CSI="\x1B["
    return CSI+"33m" + s + CSI + "0m"


def blue(s):
    CSI="\x1B["
    return CSI+"34m" + s + CSI + "0m"


def magenta(s):
    CSI="\x1B["
    return CSI+"35m" + s + CSI + "0m"


def log(msg, color=None, dobold = False):
    if color:
        msg = color(msg)
    if dobold:
        msg = bold(msg)
    print(msg, file=sys.stderr)

def execheader(name,*outputfiles, **kwargs):
    print("----------------------------------------------------",file=sys.stderr)
    if outputfiles:
        skip = True
        for outputfile in outputfiles:
            if not os.path.exists(outputfile):
                skip = False
                break
        if skip:
            log("Skipping " + name, yellow, True)
            return False
    if 'cmd' in kwargs:
        log("Calling " + name + " " + timestamp() ,white, True)
        log("Command "+ ": " + kwargs['cmd'])
    else:
        log("Calling " + name + " " + timestamp(),white, True)
    return True

def timestamp():
    return "\t" + magenta("@" + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

def execfooter(name, r, *outputfiles, **kwargs):
    if 'successcodes' in kwargs:
        successcodes = kwargs['successcodes']
    else:
        successcodes = [0]
    if r in successcodes:
        log("Finished " + name + " " + timestamp(),green,True)
    else:
        log("Runtime error from " + name + ' (return code ' + str(r) + ') ' + timestamp(),red,True)
        return False
    if outputfiles:
        error = False
        for outputfile in outputfiles:
            if os.path.exists(outputfile):
                log("Produced output file " + outputfile,green)
            else:
                log("Expected output file " + outputfile+ ", not produced!",red)
                error = True
        if error:
            return False
    return True

def runcmd(cmd, name, *outputfiles, **kwargs):
    if not execheader(name,*outputfiles, cmd=cmd): return True
    r = subprocess.call(cmd, shell=True)
    return execfooter(name, r, *outputfiles,**kwargs)

def main():
    parser = argparse.ArgumentParser(description="Evaluation")
    parser.add_argument('--matrexdir',type=str, help="Path to Matrex evaluation scripts",action='store',default="", required=True)
    parser.add_argument('--ref',type=str,help='Reference file', action='store',required=True)
    parser.add_argument('--out',type=str,help='Output file', action='store',required=True)
    parser.add_argument('--input',type=str,help='Input file', action='store',required=True)
    parser.add_argument('--debug','-d', help="Debug", action='store_true', default=False)
    #parser.add_argument('--workdir','-w',type=str,help='Work directory', action='store',default=".")
    args = parser.parse_args()

    matrexsrcfile, matrextgtfile, matrexoutfile = initevaluate(args.input, args.ref, args.out,  args.matrexdir)

    outprefix = '.'.join(args.out.split('.')[:-1])

    mtscore(args.matrexdir, matrexsrcfile, matrextgtfile, matrexoutfile, outprefix)


def initevaluate(inp, ref, out, matrexdir):

    matrexsrcfile = out.replace('.xml','') + '.matrex-src.xml'
    matrextgtfile = out.replace('.xml','') + '.matrex-ref.xml'
    matrexoutfile = out.replace('.xml','') + '.matrex-out.xml'

    inp = open(inp,'r',encoding='utf-8')
    ref = open(ref,'r',encoding='utf-8')
    out = open(out,'r',encoding='utf-8')

    inp_it = iter(inp)
    ref_it = iter(ref)
    out_it = iter(out)




    matrexsrc = open(matrexsrcfile ,'w', encoding='utf-8')
    matrextgt = open(matrextgtfile ,'w', encoding='utf-8')
    matrexout = open(matrexoutfile ,'w', encoding='utf-8')

    for t,f in (('src',matrexsrc),('ref',matrextgt),('tst',matrexout)):
        f.write( "<" + t + "set setid=\"mteval\" srclang=\"src\" trglang=\"tgt\">\n")
        f.write("<DOC docid=\"colibrita\" sysid=\"colibrita\">\n")


    count = 0

    while True:
        try:
            inp_s = next(inp_it)
            ref_s = next(ref_it)
            out_s = next(out_it)
        except StopIteration:
            break

        count += 1
        matrexsrc.write("<seg id=\"" + str(count) + "\">" + inp_s + "</seg>\n")
        matrextgt.write("<seg id=\"" + str(count) + "\">" + ref_s + "</seg>\n")
        matrexout.write("<seg id=\"" + str(count) + "\">" + out_s + "</seg>\n")


    for t,f in (('src',matrexsrc),('ref',matrextgt),('tst',matrexout)):
        f.write("</DOC>\n</" + t + "set>")
        f.close()

    return matrexsrcfile, matrextgtfile, matrexoutfile


def mtscore(matrexdir, sourcexml, refxml, targetxml, outprefix):

    per = 0
    wer = 0
    bleu = 0
    meteor = 0
    nist = 0
    ter = 0

    EXEC_MATREX_WER = matrexdir + '/eval/WER_v01.pl'
    EXEC_MATREX_PER = matrexdir + '/eval/PER_v01.pl'
    EXEC_MATREX_BLEU = matrexdir + '/eval/bleu-1.04.pl'
    EXEC_MATREX_METEOR = matrexdir + '/meteor-0.6/meteor.pl'
    EXEC_MATREX_MTEVAL = matrexdir + '/mteval-v11b.pl'
    EXEC_MATREX_TER = matrexdir + '/tercom.jar'
    EXEC_PERL = 'perl'
    EXEC_JAVA = 'java'

    errors = False
    if EXEC_MATREX_BLEU and os.path.exists(EXEC_MATREX_BLEU):
        if not runcmd(EXEC_PERL + ' ' + EXEC_MATREX_BLEU + " -r " + refxml + ' -t ' + targetxml + ' -s ' + sourcexml + ' -ci > ' + outprefix + '.bleu.score',  'Computing BLEU score'): errors = True
        if not errors:
            try:
                f = open( outprefix + '.bleu.score')
                for line in f:
                    if line[0:9] == "BLEUr1n4,":
                        bleu = float(line[10:].strip())
                        print("BLEU score: ", bleu, file=sys.stderr)
                f.close()
            except Exception as e:
                log("Error reading bleu.score:" + str(e),red)
                errors = True
    else:
        log("Skipping BLEU (no script found ["+EXEC_MATREX_BLEU+"])",yellow)

    if EXEC_MATREX_WER and os.path.exists(EXEC_MATREX_WER):
        if not runcmd(EXEC_PERL + ' ' + EXEC_MATREX_WER + " -r " + refxml + ' -t ' + targetxml + ' -s ' + sourcexml + '  > ' + outprefix + '.wer.score', 'Computing WER score'): errors = True
        if not errors:
            try:
                f = open(outprefix + '.wer.score','r',encoding='utf-8')
                for line in f:
                    if line[0:11] == "WER score =":
                        wer = float(line[12:19].strip())
                        log("WER score: " + str(wer), white)
                f.close()
            except Exception as e:
                log("Error reading wer.score:" + str(e),red)
                errors = True
    else:
        log("Skipping WER (no script found ["+EXEC_MATREX_WER+"]) ",yellow)

    if EXEC_MATREX_PER and os.path.exists(EXEC_MATREX_PER):
        if not runcmd(EXEC_PERL + ' ' + EXEC_MATREX_PER + " -r " + refxml + ' -t ' + targetxml + ' -s ' + sourcexml + '  > ' + outprefix + '.per.score',  'Computing PER score'): errors = True
        if not errors:
            try:
                f = open(outprefix +'.per.score','r',encoding='utf-8')
                for line in f:
                    if line[0:11] == "PER score =":
                        per = float(line[12:19].strip())
                        log("PER score: " + str(per), white)
                f.close()
            except Exception as e:
                log("Error reading per.score" + str(e),red)
                errors = True
    else:
        log("Skipping PER (no script found ["+EXEC_MATREX_PER+"])",yellow)

    if EXEC_MATREX_METEOR and os.path.exists(EXEC_MATREX_METEOR):
        if not runcmd(EXEC_PERL + ' -I ' + os.path.dirname(EXEC_MATREX_METEOR) + ' ' + EXEC_MATREX_METEOR + " -s colibri -r " + refxml + ' -t ' + targetxml + ' --modules "exact"  > ' + outprefix + '.meteor.score',  'Computing METEOR score'): errors = True
        if not errors:
            try:
                f = open(outprefix + '.meteor.score','r',encoding='utf-8')
                for line in f:
                    if line[0:6] == "Score:":
                        meteor = float(line[7:].strip())
                        log("METEOR score: " + str(meteor), white)
                f.close()
            except Exception as e:
                log("Error reading meteor.score:" + str(e),red)
                errors = True
    else:
        log("Skipping METEOR (no script found ["+EXEC_MATREX_METEOR+"])",yellow)

    if EXEC_MATREX_MTEVAL and os.path.exists(EXEC_MATREX_MTEVAL):
        if not runcmd(EXEC_PERL + ' ' + EXEC_MATREX_MTEVAL + " -r " + refxml + ' -t ' + targetxml + ' -s ' + sourcexml +  '  > ' + outprefix + '.mteval.score',  'Computing NIST & BLEU scores'): errors = True
        if not errors:
            try:
                f = open(outprefix + '.mteval.score','r',encoding='utf-8')
                for line in f:
                    if line[0:12] == "NIST score =":
                        nist = float(line[13:21].strip())
                        log("NIST score: ", nist)
                    if line[21:33] == "BLEU score =":
                        try:
                            bleu2 = float(line[34:40].strip())
                            if bleu == 0:
                                bleu = bleu2
                                log("BLEU score: " + str(bleu), white)
                            elif abs(bleu - bleu2) > 0.01:
                                log("blue score from MTEVAL scripts differs too much: " + str(bleu) + " vs " + str(bleu2) +  ", choosing highest score")
                                if bleu2 > bleu:
                                    bleu = bleu2
                            else:
                                log("BLEU score (not stored): " + str(float(line[34:40].strip())))
                        except:
                            raise
                f.close()
            except Exception as e:
                log("Error reading mteval.score: " + str(e),red)
                errors = True
    else:
        log("Skipping MTEVAL (BLEU & NIST) (no script found)", yellow)

    if EXEC_MATREX_TER and os.path.exists(EXEC_MATREX_TER):
        if not runcmd(EXEC_JAVA + ' -jar ' + EXEC_MATREX_TER + " -r " + refxml + ' -h ' + targetxml + '  > ' + outprefix + '.ter.score',  'Computing TER score'): errors = True
        if not errors:
            try:
                f = open(outprefix + '.ter.score','r',encoding='utf-8')
                for line in f:
                    if line[0:10] == "Total TER:":
                        ter = float(line[11:].strip().split(' ')[0])
                        log("TER score: ", ter,white)
                f.close()
            except Exception as e:
                log("Error reading ter.score: " + str(e),red)
    else:
        log("Skipping TER (no script found)",yellow)


    log("SCORE SUMMARY\n===================\n")
    f = open(outprefix + '.summary.score','w')
    s = "BLEU METEOR NIST TER WER PER"
    f.write(s+ "\n")
    log(s)
    s = str(bleu) + " " + str(meteor) + " " + str(nist)  + " " + str(ter) + " " + str(wer)  + " " + str(per)
    f.write(s + "\n")
    log(s)
    f.close()


    return not errors

if __name__ == '__main__':
    main()
