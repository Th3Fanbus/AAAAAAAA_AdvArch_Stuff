#include <iostream>
#include <vector>
#include <algorithm>

#include <tbb/tbb.h>
#include "oneapi/tbb/blocked_range.h"
#include "oneapi/tbb/parallel_for.h"

using namespace std;
using namespace oneapi;


double DotProduct(float x[],  float y[], int n)
{
   auto total = tbb::parallel_reduce(
        tbb::blocked_range<int>(0, n),
        0.0,
        [&](tbb::blocked_range<int> r, double total_acc){
            for (int i = r.begin();i<r.end();++i){
                total_acc += x[i]*y[i];
            }
            return total_acc;
        },
        plus<double>()
    );
    return total;
}

int main(){

    vector<float> x{1.,2.,3.};
    vector<float> y{3.,4.,5.};
    int size = x.size();
    
	// int size = 1000;
 //    static vector<float> x(size);
 //    static vector<float> y(size);
        
 //    generate(x.begin(), x.end(), rand);
 //    generate(y.begin(), y.end(), rand);

	tbb::tick_count t0 = tbb::tick_count::now();
 	
    double sum = DotProduct(&x[0], &y[0], x.size());
 	
    cout << "Dot product: " << sum  << endl;
 	cout << "Time: " << (tbb::tick_count::now()-t0).seconds() << "seconds" << endl;

 	return 0;

 }

