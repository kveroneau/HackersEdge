from HTMLParser import HTMLParser

ALLOWED_TAGS = ('p', 'b', 'i', 'strong',)

class HTMLChecker(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.okay = True
    def handle_starttag(self, tag, attrs):
        if tag not in ALLOWED_TAGS:
            self.okay = False
    def handle_endtag(self, tag):
        if tag not in ALLOWED_TAGS:
            self.okay = False
