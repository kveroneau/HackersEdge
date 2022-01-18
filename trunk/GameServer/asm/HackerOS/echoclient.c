#include <stdio.h>
#include <stdlib.h>
#include <conio.h>
#include "clib/heos.h"

char sock;

void netin(){
  char *buf;
  int sz;
  buf = (char*)malloc(20);
  sz = netrecv(sock, buf);
  puts(buf);
  free(buf);
  __asm__("rti");
}

int main(){
  ip_addr_t *ip_addr;
  char *ipstr;

  if (netseg() == 0){
    puts("Network offline!\n");
    return(2);
  }

  ipstr = get_param();
  ip_addr = (ip_addr_t*)malloc(sizeof(ip_addr_t));
  aton(ipstr, ip_addr);

  sock = connect(ip_addr, 23, &netin);

  if (sock == 0){
    puts("Unable to connect to port 23!\n");
    return(1);
  }

  netsend(sock, "Hello World!");
  cgetc();
  netclose(sock);

  free(ip_addr);
  return(0);
}

