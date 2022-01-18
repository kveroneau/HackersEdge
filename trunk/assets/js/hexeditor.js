// ##########################################################
// ############# START: some helper methods #################
// ##########################################################
function delegate(theFunction, thisObject, delay) {
    var wrappedFunction = function() {
        return theFunction.apply(thisObject, arguments);
    };
    if (delay != null) {
        return function() { window.setTimeout(wrappedFunction, delay); };
    } else {
        return wrappedFunction;
    }
}

function isPrintable(asciiCode) {
    return asciiCode >= 0x20 && asciiCode < 0x7f;
}

function isHexChar(c) {
    return (c >= 'A' && c <= 'F') || (c >= '0' && c <= '9');
}

function asHex(i) {
    h = i.toString(16).toUpperCase();
    return (h.length % 2 != 0)? '0' + h : h;
}

function asAscii(i) {
    return isPrintable(i)? String.fromCharCode(i) : ".";
}

function lpad(s, length, paddingChar) {
    if (paddingChar == null) {
        paddingChar = '0';
    }
    while (s.length < length)
        s = paddingChar + s;
    return s;
}

// ##########################################################
// ############## END: some helper methods ##################
// ##########################################################


// see http://www.javascripter.net/faq/keycodes.htm and http://www.quirksmode.org/js/keys.html
// Some constants for special keys
var LEFT = 37;
var UP = 38;
var RIGHT = 39;
var DOWN = 40;
var TAB = 9;

// some defaults if too few parameters are provided for the constructor
var DEFAULT_WIDTH = 16;
var DEFAULT_SIZE = 64;

// var IE="\v"=="v" // true only in IE (but not in IE9 when in HTML5 mode)
var IE = document.documentMode != null;
var NEWLINE = "\n"; // IE? "\n" : "\n";  // for IE (when not in html5 mode) \r\n is required, FF is satisfied with \n

/**
 *
 * Parameters: header, address, body, ascii must all be HTML pre elements.
 * Parameters body, ascii must have the attribute tabindex set. Otherwise they're not focusable.
 * data: Array of bytes
 * width: number of bytes per row (min 1, max 256)
 * 
 */
function ExcellentHexEditor(header, address, body, ascii, data, width) {
    var HEX_MODE = "HEX_MODE";
    var ASCII_MODE = "ASCII_MODE";

    if (data == null) {
        var len = DEFAULT_SIZE;
        data = new Array(len);
        while (--len >= 0) {
            data[len] = len % 256;
    }

    }
    if (width == null) {
        width = DEFAULT_WIDTH;
    }

    this.header = header;
    this.address = address;
    this.body = body;
    this.ascii = ascii;
    
    this.headert = header.firstChild;
    this.addresst = address.firstChild;
    this.bodyt = body.firstChild;
    this.asciit = ascii.firstChild;
    
    this.data = data;
    this.width = Math.min(Math.max(width, 1), 256); // ensure width is between 1 and 256
    
    // calculation stuff
    this.hexLength = this.width * 3 + NEWLINE.length;
    this.asciiLength = this.width + NEWLINE.length;
    
    // cursor stuff
    this.mode;
    this.nibble; // the index of the currently focused halfbyte (aka nibble)
    this.nibblePosInText; // calculated from nibble index
    this.bytePosInText;  // calculated from the nibble index (points to the first char of the byte)
    this.asciiPosInText; // calculated from the nibble index (points to the text representation of the byte currenty being edited)
    this.range; // contains the text selection which visualizes the cursor
    
    this.debug = document.getElementById('debug');
    
    this.toString = function () {
        return "ExcellentHexEditor is alive";
    }
    
    this._init = function() {
        // Note about IE9: as soon as we register any of the event listeners the keypress event is no longer being fired
        //          currently investigating....
        // Note: event handlers don't react on the pre element. Thus we register them on the surrounding DIV
        // Hack: setting the selection immediatelly after the hexeditor gets the focus doesn't work. It seems FF manipulates the selection after the focus has been set.
        //       A delay of 10ms fixes that issue.
        this.body.onfocus = delegate(function() {this._setMode(HEX_MODE); this._setSelection();}, this, 10); // event wird zwar getriggert, aber die Fokusierung geht verloren bei Navigation mit TAB Taste. Bei Mausklick geht es
        this.ascii.onfocus = delegate(function() {this._setMode(ASCII_MODE); this._setSelection();}, this, 10); // event wird zwar getriggert, aber die Fokusierung geht verloren bei Navigation mit TAB Taste. Bei Mausklick geht es
        
        // Note: for IE9 "addEventListener" must be used instead of direct assignment of the event listeners.
        //      Keep in mind, that with addEventListener the return value of the handlers is dicarded. Instead
        //      you have to call preventDefault() on the event object if you want to abort futher propagation of the event.
        //      explanation: http://bytes.com/topic/javascript/answers/157500-cant-add-return-false-addeventlistener-firefox
        this.body.addEventListener("keypress", delegate(this._keypress, this), true);
        this.ascii.addEventListener("keypress", delegate(this._keypress, this), true);
        
        this.body.addEventListener("mouseup", delegate(this._bodyonmouseup, this), true);
        this.ascii.addEventListener("mouseup", delegate(this._asciionmouseup, this), true);
        
        this._clear();
        this._display();
        this.range = document.createRange();
        this.nibble = 0;
        this._updatePositions();
        this.mode = HEX_MODE;
    }
    
    // currently just moves the curser to the end of the selection and then discards the selection
    // TODO: retain the selection but ensure that the cursor is positioned properly when user starts to type
    this._bodyonmouseup = function(e) {
        var sel = window.getSelection(); // note: for non HTML5 IE document.selection mus be used instead
        // e.rangeOffset, test.anchorOffset test.focusOffset        
        this._setMode(HEX_MODE); // ensure we're in HEX editing mode
        this.nibble = this._nibbleFrom(sel.focusOffset); // should work for both: IE and FF
        this._debug(this.nibble);
        this._updatePositions();
        this._setSelection();
    }
    
    this._asciionmouseup = function(e) {
        var sel = window.getSelection(); // note: for non HTML5 IE document.selection mus be used instead
        this._setMode(ASCII_MODE); // ensure we're in ASCII editing mode
        this.nibble = this._nibbleFromAscii(sel.focusOffset); // should work for both: IE and FF
        this._debug(this.nibble);
        this._updatePositions();
        this._setSelection();
    }
    
    this._keypress = function(e) {  
        // this is a bit tricky. See: http://www.quirksmode.org/js/keys.html
        
        var evtobj = window.event? event : e;  //distinguish between IE's explicit event object (window.event) and Firefox's implicit.
        
        // At least for Firefox 9.0.1 on windows 7 with german keyboard layout the following applies:
        // - method String.fromCharCode() returns for all printable ASCII characters (that is ascii codes 32 to 126) the proper ASCII character.
        // - the keypress event is fired prior to the keydown event
        // - the keypress event is way more useful than the keydown event, because it provides the ASCII code of the actual letter entered by the user
        //   in attribute "charCode". In the keypress event you only get the keycode for the keyboard key itself (e.g. when the user presses key A
        //   without holding shift down, you always get keycode 65 rather than 97 for the lowercase a.
        // - When one of the arrow keys is pressed, attribute keycode is set and attribute charcode is 0. That's useful for telling apart whether the user
        //   pressed an arrow key or entered one of the chars %, &, ' etc. (Background: charcode for % is 37, keycode for arrow left is also 37)
        var charcode = IE? evtobj.keyCode : evtobj.charCode;
        var keycode = (!IE)? evtobj.keyCode : 0;
        
        // TODO: INS, DEL, COPY-PASTE
        
        // control keys
        if (keycode != 0) {
            switch (keycode) {
                case LEFT:
                    this._moveCursor((this.mode == HEX_MODE)? -1 : -2);
                    return true;
                case RIGHT:
                    this._moveCursor((this.mode == HEX_MODE)? 1 : 2);
                    return true;
                case UP:
                    this._moveCursor(-1 * this.width * 2);
                    return true;
                case DOWN:
                    this._moveCursor(this.width * 2);
                    return true;
                case TAB:
                    return true;
                default:
                    break;
            }
        }
        
        else if (charcode != 0) {
            // other keys
            switch(this.mode) {
                case HEX_MODE: 
                    this._handleHex(charcode);
                    break;
                case ASCII_MODE:
                    this._handleAscii(charcode);
                    break;
                default:
                    break;
            }
            // SHIFT+7 (which is forward slash) also triggers the search in Firefox which causes the focus to be removed from the hexeditor. 
            // By returning FALSE / calling preventDefault this doesn't happen.
            if (evtobj.preventDefault) { evtobj.preventDefault(); }
            return false; 
        }
        
        return true;
    }
    
    /**
     * VERSION 2
     */
    this._handleHex = function(unicode) {
        var c = String.fromCharCode(unicode);
        c = c.toUpperCase();
        if (isHexChar(c)) {
            // update HEX representation
            this.bodyt.replaceData(this.nibblePosInText, 1, c);
            
            // update the ASCII representation
            var byteAddress = Math.floor(this.nibble / 2);
            var hexValue = this.bodyt.data.substr(this.bytePosInText, 2);
            var value = parseInt(hexValue, 16);
            this.asciit.replaceData(this.asciiPosInText, 1, asAscii(value));
            
            // Move cursor by one nibble
            this._moveCursor();
        }
    }
    
    /**
     * VERSION 2
     */
    this._handleAscii = function(unicode) {
        if (!isPrintable(unicode)) {
            return;
        }
    
        // update the ASCII representation
        this.asciit.replaceData(this.asciiPosInText, 1, asAscii(unicode));
        
        // update HEX representation
        this.bodyt.replaceData(this.nibblePosInText, 2, asHex(unicode));
        
        // Move cursor by two nibbles
        this._moveCursor(2);
    }
    
    /**
     * VERSION 2
     */
    this._setMode = function(mode) {
        this.mode = mode;
        // when switched from HEX_MODE to ASCII_MODE move the cursor the first nibble of the byte currently being edited
        //      --> makes cursor handling way easier
        if (this.mode == ASCII_MODE && ((this.nibble % 2) != 0)) {
            this._moveCursor(-1);
        }
    }
    
    this._nibbleFrom = function(textPosition) {
        var row = Math.floor(textPosition / this.hexLength);
        var offset = textPosition % this.hexLength;
        return (row * this.width * 2) + (Math.floor(offset / 3) * 2) + (offset % 3 > 0);
    }
    
    this._nibbleFromAscii = function(textPosition) {
        var row = Math.floor(textPosition / this.asciiLength);
        var offset = textPosition % this.asciiLength;
        return (row * this.width * 2) + (offset * 2);
    }
    
    /**
     * VERSION 2
     */
    this._setCursor = function(nibble) {
        this.nibble = nibble;
        this._updatePositions();
        this._setSelection();
    }
    
    /**
     * VERSION 2
     */
    this._moveCursor = function(offset) {
        if (offset == null)
            offset = 1;
        this.nibble += offset;
        
        // ensure cursor is within bounds
        if (this.nibble < 0) {
            this.nibble = 0;
        }
        if (this.nibble >= this.data.length * 2) {
            this.nibble = (this.data.length * 2) - 1;
        }
        
        this._updatePositions(); 
        this._setSelection();
    }
    
    // the selection isn't applied when the hexeditor pane gets the focus
    // VERSION 2
    this._setSelection = function() {
        try {
            window.getSelection().removeAllRanges(); // removeRange(this.range);
        } catch (e){};
        if (this.mode == HEX_MODE) {
            this.range.setStart(this.bodyt, this.nibblePosInText);
            this.range.setEnd(this.bodyt, this.nibblePosInText + 1);
        } else if (this.mode == ASCII_MODE) {
            this.range.setStart(this.asciit, this.asciiPosInText);
            this.range.setEnd(this.asciit, this.asciiPosInText + 1);
        }
        window.getSelection().addRange(this.range); 
        ((this.mode == HEX_MODE)? this.body : this.ascii).focus(); // Hack for IE9: everytime the setSelection is called IE shows a search icon and focus is lost
        return true;
    }
    
    /**
     * VERSION 2
     */
    this._updatePositions = function() {
        var address = Math.floor(this.nibble / 2);
        var row = Math.floor(address / this.width);
        var column = address % this.width;
        
        this.nibblePosInText = (row * this.width * 3) + row + (column * 3) + (this.nibble % 2 == 1);
        this.bytePosInText = ((this.nibble % 2) == 0)? this.nibblePosInText : this.nibblePosInText - 1;
        this.asciiPosInText = (row * this.width) + row + column;
    }
    
    /**
     * VERSION 2
     */
    this._clear = function() {
        this.headert.deleteData(0, this.headert.nodeValue.length);
        this.addresst.deleteData(0, this.addresst.nodeValue.length);
        this.bodyt.deleteData(0, this.bodyt.nodeValue.length);
        this.asciit.deleteData(0, this.asciit.nodeValue.length);
    }
    
    /**
     * Displays the binary document initially
     * VERSION 2
     */
    this._display = function() {
        var buf = "";
        
        // print header row
        buf = "";
        for (i = 0; i < width; i++) {
            buf += asHex(i) + " ";
        }
        buf = buf.substr(0, buf.length - 1); // remove trailing blank
        this.headert.insertData(0, buf);
        
        // print addresses
        var lengthOfAddress = asHex(this.data.length - 1).length;   
        buf = "";
        for(i = 0; i < this.data.length; i += this.width) {
            buf += lpad(asHex(i), lengthOfAddress);
            buf += NEWLINE;
        }
        this.addresst.insertData(0, buf);
        
        // print hex and ASCII
        var buf = "";
        var abuf = "";
        for(i = 0; i < this.data.length; i++) {
            if (i != 0 && (i % this.width == 0)) {
                // new row
                buf += NEWLINE;
                abuf += NEWLINE;
            }
            
            buf += asHex(this.data[i]) + " ";
            abuf += asAscii(this.data[i]);
        }
        this.bodyt.insertData(0, buf);
        this.asciit.insertData(0, abuf);
    }
    
    this._debug = function(message, wrap) {
        this.debug.value += message + ",";
        if (wrap) {
            this.debug.value += "\n";
        }
    }
    
    this._init();
}
