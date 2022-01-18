// Hacker's Edge JavaScript/WebSockets client code.
function extend(subClass, baseClass) {
	function inheritance() { }
	inheritance.prototype          = baseClass.prototype;
	subClass.prototype             = new inheritance();
	subClass.prototype.constructor = subClass;
	subClass.prototype.superClass  = baseClass.prototype;
};

function HackersEdge(ws_url, container) {
	this.ws_url = ws_url;
	this.pendingKeys  = '';
	this.keysInFlight = false;
	this.connected    = false;
	this.superClass.constructor.call(this, container);
	this.vt100("Connecting to Hacker's Edge...");
	this.ws = new WebSocket('ws://'+ws_url);
	this.ws.onopen = function(evt) { client.vt100('connected.\r\n'); client.connected = true; };
	this.ws.onclose = function(evt) { client.sessionClosed(); };
	this.ws.onmessage = function(evt){
	  var resp = client.vt100(evt.data);
	  if (resp){ client.ws.send(resp); }
	  client.keysInFlight = false;
	};
	this.ws.onerror = function(evt){ client.vt100('\r\nUnable to contact server.\r\n'); };
};

extend(HackersEdge, VT100);

HackersEdge.prototype.sessionClosed = function() {
	try {
		this.connected    = false;
	    if (this.session) {
	    	this.session    = undefined;
	    	if (this.cursorX > 0) {
	    		this.vt100('\r\n');
	    	}
	    	this.vt100('Session closed.');
	    }
	    this.showReconnect(true);
	} catch (e) {
	}
};

HackersEdge.prototype.reconnect = function() {
	this.showReconnect(false);
	this.pendingKeys     = '';
	this.keysInFlight    = false;
	this.reset(true);
	this.vt100("Connecting to Hacker's Edge...");
	this.ws = new WebSocket('ws://'+this.ws_url);
	this.ws.onopen = function(evt) { client.vt100('connected.\r\n'); client.connected = true; };
	this.ws.onclose = function(evt) { client.sessionClosed(); };
	this.ws.onmessage = function(evt){
	  var resp = client.vt100(evt.data);
	  if (resp){ client.ws.send(resp); }
	  client.keysInFlight = false;
	};
	this.ws.onerror = function(evt){ client.vt100('\r\nUnable to contact server.\r\n'); };
};

HackersEdge.prototype.sendKeys = function(keys) {
	if (!this.connected) { return; }
	this.ws.send(keys);
};

HackersEdge.prototype.keysPressed = function(ch) {
	this.sendKeys(ch);
};

suppressAllAudio = true;
