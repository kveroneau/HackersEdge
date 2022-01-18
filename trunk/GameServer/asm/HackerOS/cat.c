#include <stdio.h>
#include <stdlib.h>
#include <conio.h>
#include <peekpoke.h>
#include "clib/heos.h"

int main() {
  char* fname;
  int sz;
  int i;

  fname = get_param();
  sz = load_file(fname, 0xf500);
  if (sz == 0){
    return(1);
  }
  for (i=0;i<sz;i++){
    cputc(PEEK(0xf500+i));
  }
  cputc('\n');
  return(0);
}