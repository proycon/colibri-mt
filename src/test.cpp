#include <pattern.h>
#include <alignmodel.h>

using namespace std;

void test(bool r) {
    if (r) {
        cerr << string( ".... ok") << endl;
    } else {
        cerr << ".... FAILED!" << endl;
        exit(2);
    }
}



int main( int argc, char *argv[] ) {
	//string model = argv[1];
	//string classfile = argv[1];
    Pattern pattern = Pattern();
    return 0;
}
