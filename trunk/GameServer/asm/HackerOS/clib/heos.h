typedef unsigned long ip_addr_t;

extern char* get_param();
extern int load_file(const char* filename, int addr);
extern int save_file(const char* filename, int addr, int filesize);
extern char netseg();
extern char listen(char port, int addr);
extern void netclose(char sock);
extern void netreply(const char* data);
extern void netsend(char sock, const char* data);
extern char connect(const ip_addr_t* ip_addr, char port, int addr);
extern int netrecv(char sock, char* buffer);
extern void aton(const char* src, ip_addr_t* ip_addr);
extern void ntoa(const ip_addr_t* ip_addr, char* dest);
extern char ca65(int addr, int filesize);
extern char cc65(int addr, int filesize);

