#include <stdio.h>
#include <stdlib.h>
#include <conio.h>
#include "clib/heos.h"

void netin(){
  netreply("Hello World!");
  __asm__("rti");
}

int main(){
  char sock;
  
  if (netseg() == 0){
    puts("Network offline!\n");
    return(2);
  }
  
  sock = listen(23, &netin);
  if (sock == 0){
    puts("Unable to bind to port.\n");
    return(1);
  }
  
  puts("Listening on port 23.\nPress ENTER to stop.");
  cgetc();
  
  netclose(sock);
}
