#include <iostream>
#include <vector>
#include <algorithm>

#include <tbb/tbb.h>
#include "oneapi/tbb/task_group.h"

using namespace std;
using namespace oneapi;

int Fib(int n) {
     if (n<2) {
        return n;
     } else {
        int x, y;
        tbb::task_group g;
        
        g.run([&]{
            x=Fib(n-1);}
        ); 
        g.run([&]{
            y=Fib(n-2);}
        ); 
        
        g.wait(); // wait for both tasks to complete
        return x+y;
     }
 }

// int Fib2(int n) { 
//      if (n<2) {
//         return n;
//      } else {
//         int x, y;
        
//         tbb:paralle_invoke(
//             x=Fib(n-1);,
//             y=Fib(n-2);
//         );
//         // can we wait with parallel_invoke?
//         return x+y;
//      }
//  }

int main(){

    static int n = 10;
    
	tbb::tick_count t0 = tbb::tick_count::now();
 	
    int res = Fib(n);

    cout << " Fibonacci("<< n <<")= " << res << endl;
   
 	cout << "\nTime: " << (tbb::tick_count::now()-t0).seconds() << "seconds" << endl;

 	return 0;

 }
