#include <lm.h>


using namespace std;

LanguageModel::LanguageModel(const std::string & filename, ClassEncoder & encoder, ClassDecoder * classdecoder, bool debug) {
    this->DEBUG = debug; 
    this->classdecoder = classdecoder;
    order = 0;
    bool hasunk = false;
    ifstream f;    
    f.open(filename.c_str(), ios::in);
    if ((!f) || (!f.good())) {
       cerr << "File does not exist: " << filename << endl;
       exit(3);
    }    
    while (!f.eof()) {               
        string line;
        getline(f, line);                
        if (line == "\\data\\") {
            order = 0;
        } else if (line == "\\1-grams:") { //bit inelegant, but simplest
            order = 1;
        } else if (line == "\\2-grams:") {
            order = 2;
        } else if (line == "\\3-grams:") {
            order = 3;            
        } else if (line == "\\4-grams:") {
            order = 4;
        } else if (line == "\\5-grams:") {
            order = 5;            
        } else if (line == "\\6-grams:") {
            order = 6;            
        } else if (line == "\\7-grams:") {
            order = 7;            
        } else if (line == "\\8-grams:") {
            order = 8;            
        } else if (line == "\\9-grams:") {
            order = 9;                        
        } else if (!line.empty()) {
            if (order == 0) {
              if (line.substr(0,5) == "ngram") {
                string n_s = line.substr(6,1);
                string v_s = line.substr(8);
                int n = atoi(n_s.c_str());
                int v = atoi(v_s.c_str());
                total[n] = v;
              }   
            } else if (order > 0) {
                string logprob_s = "";
                string backofflogprob_s = "";
                string ngramcontent = "";
                int fields = 0;
                int begin = 0;
                for (unsigned int i = 0; i  <= line.length(); i++) {
                    if ((line[i] == '\t') || (line[i] == '\n') || (i == line.length())) {
                        if (fields == 0) {
                            logprob_s = line.substr(begin, i - begin);
                        } else if (fields == 1) {
                            ngramcontent = line.substr(begin, i - begin);
                        } else if (fields == 2) {
                            backofflogprob_s = line.substr(begin, i - begin);
                        }
                        begin = i + 1;
                        fields++;
                    }
                }
                
                
                if ((!logprob_s.empty()) && (!ngramcontent.empty())) {
                    if (ngramcontent == "<unk>") {
                        ngrams[UNKPATTERN] = atof(logprob_s.c_str()) * log(10); //* log(10) does log10 to log_e conversion
                        hasunk = true;
                        if (DEBUG) {
                            cerr << " Adding UNKNOWN to LM: " << (int) UNKPATTERN.n() << "\t" <<  ngramcontent << "\t" << ngrams[UNKPATTERN] << endl;
                        }
                    } else {
                        Pattern ngram = encoder.buildpattern(ngramcontent);
                        if (!ngram.unknown()) {
                            ngrams[ngram] = atof(logprob_s.c_str()) * log(10); //* log(10) does log10 to log_e conversion
                            if (!backofflogprob_s.empty()) {
                                backoff[ngram] = atof(backofflogprob_s.c_str()) * log(10); //* log(10) does log10 to log_e conversion
                                if (DEBUG) cerr << " Adding to LM: " << (int) ngram.n() << "\t" <<  ngramcontent << "\t" << ngrams[ngram] << "\t" << backoff[ngram] << endl;
                            } else {
                                if (DEBUG) cerr << " Adding to LM: " << (int) ngram.n() << "\t" << ngramcontent << "\t" << ngrams[ngram] << endl;
                            }
                        }
                    }
                } else {
                    cerr << "WARNING: Ignoring line: " << line << endl;
                }
            } else {
                cerr << "WARNING: Don't know what to do with line: " << line << endl;
            }
        }
        
    }
    f.close();
    
    if (!hasunk) {
        cerr << "ERROR: Language Model has no value <unk>, make sure to generate SRILM model with -unk parameter" << endl;
        exit(3);
    }
}


double LanguageModel::score(const Pattern * ngram, const Pattern * history) { //returns logprob (base 10)
    
    if (DEBUG) {
        if (history == NULL) {
            cerr << "\t\t\tLM DEBUG: score(): history=NULL ngram='" << ngram->tostring(*classdecoder) << "'" << endl;
        } else {
            cerr << "\t\t\tLM DEBUG: score(): history='" << history->tostring(*classdecoder) << "' ngram='" << ngram->tostring(*classdecoder) << "'" << endl;
        }
    }  
    double result = 0;
    const int n = ngram->n();       
    for (int i = 0; i < n; i++) {
        Pattern * word =  new Pattern(ngram,i,1);
        Pattern * newhistory = NULL;
        if ((i >= order-1) || ((i > 0) && (history == NULL))) {
            //new history can be fetched from ngram alone
            int begin = i - (order - 1);
            if (begin < 0) begin = 0;              
            newhistory = new Pattern(ngram,begin,i-begin);            
        } else if (history != NULL) {
            //new history has to be fetched from old history and ngram
            Pattern * slice = NULL;
            if (i > 0) slice = new Pattern(ngram,0,i);
            const int leftover = order - 1 - i;
            if (leftover > 0) {
                Pattern * historyslice = new Pattern(history, history->n() - leftover, leftover);
                if (slice == NULL) {
                    newhistory = historyslice;
                } else {   
                    newhistory = new Pattern(*historyslice + *slice);
                    delete historyslice;
                }            
            } 
            if (slice != NULL) delete slice;
        }
        
        result += scoreword(word, newhistory);
         
        delete word;
        if (newhistory != NULL) delete newhistory;
    }
    if (DEBUG) cerr << "\t\t\tLM DEBUG: score() = " << result << endl;
    return result; 
}

double LanguageModel::scoreword(const Pattern * word, const Pattern * history) {

    if (DEBUG) {
        if (history == NULL) {
            cerr << "\t\t\tLM DEBUG: scoreword(): history=NULL word='" << word->tostring(*classdecoder) << "'" << endl;
        } else {
            cerr << "\t\t\tLM DEBUG: scoreword(): history='" << history->tostring(*classdecoder) << "' word='" << word->tostring(*classdecoder) << "'" << endl;
        }
    }  

    const Pattern * lookup;
    
    if (history != NULL) {
        lookup = new Pattern( *history + *word);
    } else {
        lookup = word;
    }
    const int n = lookup->n();
    PatternMap<double>::iterator iter = ngrams.find(*lookup);
         
    if (iter != ngrams.end()) {
        if (DEBUG) cerr << "\t\t\tLM DEBUG: scoreword(): Found " << n << "-gram, score=" << iter->second << endl;
        if (history != NULL) delete lookup;        
        return iter->second;        
    } else {
        if (DEBUG) cerr << "\t\t\tLM DEBUG: scoreword(): " << n << "-gram not found. Backing off..." << endl;        
    }
    
    if (history != NULL) delete lookup;
    
         
    //not found, back-off    
    double result = 0;

    double backoffweight = 0; //backoff weight will be 0 if not found 
    /*
    Not all N-grams in the model file have backoff weights. The highest order N-grams do not need a backoff weight. For lower order N-grams backoff weights are only recorded for those that appear as the prefix of a longer N-gram included in the model. For other lower order N-grams the backoff weight is implicitly 1 (or 0, in log representation).
    */    

    if (history != NULL) {
        //ngram not found: back-off: alpha(history) * p(n-1)    


        const int history_n = history->n();
                    
        Pattern * newhistory;        
    
        
        if (history_n > 1) { 
            newhistory =  new Pattern(history, 1,history_n-1);    
        } else {
            newhistory = NULL;
        }
        PatternMap<double>::iterator iter = backoff.find(*history);
        if (iter != backoff.end()) {
            if (DEBUG) cerr << "\t\t\tLM DEBUG: backoffpart=" << iter->first.tostring(*classdecoder) << " = " << iter->second << endl;
            backoffweight = iter->second;        
        }
        //if (DEBUG) cerr << "LM DEBUG: scoreword(): Backoffpart=" << backoffpart->decode(*classdecoder) << endl;
              
        
        if (DEBUG) cerr << "\t\t\tLM DEBUG: scoreword(): Backoffweight=" << backoffweight << endl;
        result = backoffweight + scoreword(word, newhistory);
        if (DEBUG) cerr << "\t\t\tLM DEBUG: scoreword() =" << result << endl;
        if (newhistory != NULL) delete newhistory;
        
    } else {
        cerr << "INTERNAL ERROR: LanguageModel::scoreword() ... unigram not found, and no history.. this should not happen" << endl;
        exit(6);
    }    
    return result;
}


