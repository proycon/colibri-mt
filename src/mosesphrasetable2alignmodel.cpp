#include <string>
#include <vector>
#include <iostream>
#include <fstream>
#include <getopt.h>
#include <classencoder.h>
#include <classdecoder.h>
#include <pattern.h>
#include <patternmodel.h>
#include <alignmodel.h>
#include <gzstream.h>

using namespace std;

class BufferItem {
    public:
     Pattern sourcepattern;
     Pattern targetpattern;
     vector<double> scores;

     BufferItem(const Pattern & sourcepattern, const Pattern & targetpattern, const vector<double> & scores) {
        this->sourcepattern = sourcepattern;
        this->targetpattern = targetpattern;
        this->scores = scores;
    }
};

void loadmosesphrasetable(PatternAlignmentModel<double> & model,  const std::string & filename, ClassEncoder & sourceencoder, ClassEncoder & targetencoder, PatternSetModel * constrainsourcemodel = NULL, PatternSetModel * constraintargetmodel = NULL, int max_sourcen =0, const double pts=0, const double pst=0, const double joinedthreshold=0, const double divergencefrombestthreshold=0.0, const std::string delimiter = "|||", const int score_column=3, const int pstfield = 0, const int ptsfield=2, const int maxscores = 10)
  {
    unsigned int added = 0;
    unsigned int skipped = 0;
    unsigned int constrained = 0;
    unsigned int count = 0;

    PatternSetModel firstwords;
    if (constrainsourcemodel != NULL) {
        cerr << "(Inferring extra contraints from source model, for faster discarding of patterns)" << endl;
        for (PatternSetModel::iterator iter = constrainsourcemodel->begin(); iter != constrainsourcemodel->end(); iter++) {
            const Pattern pattern = *iter;
            const Pattern firstword = pattern[0];
            firstwords.insert(firstword);
        }
        cerr << "(added " << firstwords.size() << " unigrams)" << endl;
    }

    //load from moses-style phrasetable file
    istream * f = NULL;
    if (filename.substr(filename.size()-3) == ".gz") {
        cerr << "(Reading from gzip)" << endl;
        f = new igzstream(filename.c_str(), ios::in | ios::binary);
    } else {
        f = new ifstream(filename.c_str(), ios::in | ios::binary);
    }
    if ((f == NULL) || (!f->good())) {
       cerr << "File does not exist: " << filename << endl;
       exit(2);
    }

    vector<BufferItem> buffer;

    string firstword;
 
    bool skipsamesource = false;
    string prevsource;
    string skipfirstword;

    string source = "";
    string target = "";
    string scores_s;
    bool abort = false;
    int mode = 0;
    int begin = 0;
    bool updated = false;
    string line;
    vector<double> scores;

    while (!f->eof()) {
        line.clear();
        getline(*f, line);
        count++;
        if (count % 100000 == 0) {
            cerr << endl;
            cerr <<  "Loading and encoding phrase-table: @" << count << " total added: " << added  << ", skipped because of threshold: " << skipped << ", skipped because of constraints: " << constrained;            
        }
        if (count % 1000 == 0) {
            if (updated) {
                cerr << ":";
            } else {
                cerr << ".";
            }
            updated = false;
        }
        mode = 0;
        abort = false;
        begin = 0;
        source.clear();
        target.clear();
        scores_s.clear();
        const int linesize = line.size();
        for (unsigned int i = 0; i < linesize; i++) {
            if (line.substr(i,5) == " ||| ") {
                if (mode == 0) {
                    source = line.substr(begin, i - begin);
                    int j = 0;
                    firstword = source;
                    for (auto c : source) {
                        if (c == ' ') {
                            firstword = source.substr(0,j);
                            break;
                        }
                        j++;
                    }
                    if (firstword == skipfirstword) {
                        abort = true;
                        break;
                    }
                } else if (mode == 1) {
                    target = line.substr(begin, i - begin);
                } else if (mode == 2) {
                    scores_s = line.substr(begin, i - begin);
                }
                begin = i+5;
                mode++;
            }
        }
        if (mode != 3) {
            cerr << "Error in input format, line " << count << endl;
        }
        cerr << "DEBUG: read " << source << " -- " << target << endl;

        if ((abort) || (firstword == skipfirstword)) {
            constrained++;
            continue;
        } else if ((skipsamesource) && (source == prevsource)) {
            constrained++;
            continue;
        } else {
            skipsamesource = false;
            skipfirstword = "";
        }

        scores.clear();
        scores_s = scores_s + " ";
        begin = 0;
        //cerr << "DEBUG: scores_s=" << scores_s << endl;
        for (unsigned int i = 0; i < scores_s.size(); i++) {
            if ((scores_s[i] == ' ')  && (i > begin)) {
                double score = atof(scores_s.substr(begin, i - begin).c_str());
                //cerr << scores_s.substr(begin, i - begin) << " -> " << score << endl;
                scores.push_back(score);
                begin = i + 1;
            }
        }

        if (((!buffer.empty()) && (source != prevsource))) {
            if (buffer.size() >= 100) {
                cerr << "!";
            }
            if (divergencefrombestthreshold > 0) {
                double bestscore = 0;
                for (auto bufferitem : buffer) {
                    if (bufferitem.scores[ptsfield] > bestscore) bestscore = bufferitem.scores[ptsfield];
                }

                double p = bestscore * divergencefrombestthreshold;
                for (auto bufferitem : buffer) {
                    if (bufferitem.scores[ptsfield] >= p) {
                        model.add( bufferitem.sourcepattern, bufferitem.targetpattern, bufferitem.scores );
                        added++;
                        updated = true;
                    } else {
                        skipped++;
                    }
                }
            } else {
                for (auto bufferitem : buffer) {
                    model.add( bufferitem.sourcepattern, bufferitem.targetpattern, bufferitem.scores );
                    added++;
                    updated = true;
                }
            }
            buffer.clear();
        }

        if ((source.empty()) || (target.empty()) || (scores.empty())) continue;

        //check score threshold
        if (  ((pst > 0) && (scores[pstfield] < pst))
            || ((pts > 0) && (scores[ptsfield] < pts))
            || ((joinedthreshold > 0) && (scores[ptsfield] * scores[pstfield] < joinedthreshold))
        ) {
            skipped++;
        } else {
            //add to phrasetable
            Pattern sourcepattern = sourceencoder.buildpattern(source);

            if ((constrainsourcemodel != NULL) && (!constrainsourcemodel->has(sourcepattern))) {
                const int _n = sourcepattern.n();
                if (_n == 1) {
                    skipfirstword = firstword;
                } else if (!firstwords.has(sourcepattern[0])) {
                    skipfirstword = firstword;
                }

                constrained++;
                skipsamesource = true;
                continue;
            }

            if ((max_sourcen > 0) && (sourcepattern.n() > max_sourcen)) {
                skipped++;
                skipsamesource = true;
                continue;
            }

            Pattern targetpattern = targetencoder.buildpattern(target);

            if ((constraintargetmodel != NULL) && (!constraintargetmodel->has(targetpattern))) {
                constrained++;
                continue;
            }

            if (scores.size() > maxscores) {
                cerr << endl << "*** WARNING: Unexpectedly large number of scores in line " << count << ", something wrong? ***" << endl;
            }

            buffer.push_back( BufferItem(sourcepattern, targetpattern, scores) );
        }

    }

    //don't forget last one in buffer:
    if (!buffer.empty()) {
        if (divergencefrombestthreshold > 0) {
            double bestscore = 0;
            for (auto bufferitem : buffer) if (bufferitem.scores[ptsfield] > bestscore) bestscore = bufferitem.scores[ptsfield];

            double p = bestscore * divergencefrombestthreshold;
            for (auto bufferitem : buffer) {
                if (bufferitem.scores[ptsfield] >= p) {
                    model.add( bufferitem.sourcepattern, bufferitem.targetpattern, bufferitem.scores );
                    added++;
                } else {
                    skipped++;
                }
            }
        } else {
            for (auto bufferitem : buffer) {
                model.add( bufferitem.sourcepattern, bufferitem.targetpattern, bufferitem.scores );
                added++;
            }
        }
        buffer.clear();
    }
    cerr << "Added: " << added << " -- skipped due to threshold: " << skipped << " -- skipped by constraint: " << constrained << endl;
    cerr << "Source patterns: " << model.size() <<  endl;
}

void usage() {
     cerr << "Syntax: colibri-mosesphrasetable2alignmodel -i [mosesphrasetable] -o [outputfile] -S [sourceclassfile] -T [targetclassfile]" << endl;
     cerr << "Further options:" << endl;
     cerr << "-p [double]            p(t|s) threshold" << endl;
     cerr << "-P [double]            p(s|t) threshold" << endl;
     cerr << "-j [double]            p(s|t) * p(t|s) threshold" << endl;
     cerr << "-d [double]            divergence from best threshold, prunes translation options lower than set threshold times the strongest translation options (prunes weaker alternatives)" << endl;
     cerr << "-m [patternmodel]      Constrain source-patterns by this pattern model" << endl;
     cerr << "-M [patternmodel]      Constrain target patterns by this pattern model" << endl;
     cerr << "-t [int]               Only consider patterns from constraint model that occur at least this many times (default: 1)" << endl;
     cerr << "-l [int]               Only consider patterns from constraint model that are not longer than the specified length" << endl;
     cerr << "-w                     Output model to stdout" << endl;
}

int main( int argc, char *argv[] ) {
    string mosesfile = "";
    string outputfile = "";
    string sourceclassfile = "";
    string targetclassfile = "";
    string sourceconstrainfile = "";
    string targetconstrainfile = "";

    double divergencefrombestthreshold = 0.0;
    double joinedthreshold = 0.0;
    double pts = 0.0;
    double pst = 0.0;

    bool writestdout = false;

    PatternModelOptions constrainoptions;
    constrainoptions.MINTOKENS = 1;
    constrainoptions.MAXLENGTH = 99;

    char c;
    while ((c = getopt(argc, argv, "i:o:S:T:hp:P:j:d:m:M:t:l:w")) != -1)
         switch (c) {
            case 'h':
                usage();
                exit(0);
            case 'S':
                sourceclassfile = optarg;
                break;
            case 'T':
                targetclassfile = optarg;
                break;
            case 'i':
                mosesfile = optarg;
                break;
            case 'o':
                outputfile = optarg;
                break;
            case 'm':
                sourceconstrainfile = optarg;
                break;
            case 'M':
                targetconstrainfile = optarg;
                break;
            case 'p':
                pts = atof(optarg);
                break;
            case 'P':
                pst = atof(optarg);
                break;
            case 'j':
                joinedthreshold = atof(optarg);
                break;
            case 'd':
                divergencefrombestthreshold = atof(optarg);
                break;
            case 't':
                constrainoptions.MINTOKENS = atoi(optarg);
                break;
            case 'l':
                constrainoptions.MAXLENGTH = atoi(optarg);
                break;
            case 'w':
                writestdout = true;
                break;
            case '?':
            default:
                cerr << "ERROR: Unknown option, usage:" << endl;
                usage();
                exit(2);
        }
    
    if (mosesfile.empty() || (outputfile.empty() && !writestdout) || sourceclassfile.empty() || targetclassfile.empty()) {
            cerr << "ERROR: Missing required options, usage:" << endl;
            usage();
            exit(2);
    }


    cerr << "Loading source encoder " << sourceclassfile << endl;
    ClassEncoder sourceencoder = ClassEncoder(sourceclassfile);
    cerr << "Loading target encoder " << targetclassfile << endl;
    ClassEncoder targetencoder = ClassEncoder(targetclassfile);

    PatternSetModel * sourceconstrainmodel = NULL;
    if (!sourceconstrainfile.empty()) {
        cerr << "Loading source constraint model " << sourceconstrainfile << endl;
        sourceconstrainmodel = new PatternSetModel(sourceconstrainfile, constrainoptions);
        cerr << "(Loaded " << sourceconstrainmodel->size() << " patterns)" << endl;
    }

    PatternSetModel * targetconstrainmodel = NULL;
    if (!targetconstrainfile.empty()) {
        cerr << "Loading target constraint model " << targetconstrainfile << endl;
        targetconstrainmodel = new PatternSetModel(targetconstrainfile, constrainoptions);
        cerr << "(Loaded " << targetconstrainmodel->size() << " patterns)" << endl;
    }

    PatternAlignmentModel<double> model = PatternAlignmentModel<double>();
    
    cerr << "Loading moses phrasetable " << mosesfile << endl;
    loadmosesphrasetable(model, mosesfile,  sourceencoder,  targetencoder,  sourceconstrainmodel,  targetconstrainmodel , constrainoptions.MAXLENGTH, pts, pst,joinedthreshold,  divergencefrombestthreshold);

    if (!outputfile.empty()) {
        cerr << "Writing output file" << endl;
        model.write(outputfile);
    } 

    if (writestdout) {
        cerr << "Loading source decoder " << sourceclassfile << endl;
        ClassDecoder sourcedecoder = ClassDecoder(sourceclassfile);
        cerr << "Loading target decoder " << targetclassfile << endl;
        ClassDecoder targetdecoder = ClassDecoder(targetclassfile);

        model.print((ostream*) &cout, sourcedecoder, targetdecoder);
    }

    cerr << "Done" << endl;
    exit(0);
}
