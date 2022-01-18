<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:import href="base.xsl"/>

  <xsl:template match="/">
    <html>
      <head>
        <meta charset="utf-8"/>
        <xsl:if test="page/@href">
          <meta http-equiv="refresh" content="0; url=/index.xml#{page/@href}"/>
        </xsl:if>
        <title>Hacker's Edge | <xsl:value-of select="page//@title"/></title>
        <link type="text/css" href="{page/@assets}css/bootstrap.min.css" rel="stylesheet" />
        <link type="text/css" href="{page/@assets}css/trontastic/jquery-ui-1.8.18.custom.css" rel="stylesheet" />
        <link type="text/css" href="{page/@assets}css/style.css" rel="stylesheet" />
        <link href="{page/@assets}css/vt100.css" rel="stylesheet"/>
        <style>
        .jtable tr .ui-state-hover { font-weight: normal; }
        </style>
        <xsl:if test="page/css">
          <style><xsl:value-of select="page/css"/></style>
        </xsl:if>
        <script src="{page/@assets}js/jquery-1.7.1.min.js" type="text/javascript"></script>
        <script src="{page/@assets}js/jquery-ui-1.8.18.custom.min.js" type="text/javascript"></script>
        <script src="{page/@assets}js/m-xml.min.js" type="text/javascript"></script>
        <script src="{page/@assets}js/vt100.js"></script>
        <script src="{page/@assets}js/client.js"></script>
        <script type="text/javascript">
$(function(){
  $("#message").hide();
  $("#navbar a").button();
  $("#accordion").accordion({fillSpace:true});
  $("button").button({icons:{primary:"ui-icon-trash"}});
  xlink = function(xml,xid){
    if (xid != 'ctx'){
      if (xid == 'hash'){ xid = 'ctx'; }
      var content = document.getElementById(xid);
      content.innerHTML = '';
      content.appendChild(magicXML.transform(xml,'<xsl:value-of select="page/@assets"/>xsl/base.xsl'));
      $(".btn").button();
      magicXML.parse(".mxml");
      $("#accordion").accordion({fillSpace:true});
      return false;
    }else{ return true; }
  };
  postok = function(data){
    if (data.st == 'xlink'){
      xlink(data.xml, data.id);
    }else if (data.st == 'error'){
      alert(data.msg);
    }
  };
  if (window.location.hash.substr(1) != ''){ xlink(window.location.hash.substr(1), 'hash'); }
  window.onhashchange = function(){ xlink(window.location.hash.substr(1), 'hash'); }
});
        </script>
      </head>
      <body>
        <div class="container">
          <div id="navbar" class="row">
            <div class="span3" id="brand">Hacker's Edge</div>
            <xsl:for-each select="page/navbar/item">
              <div class="span1"><a href="#{.}" onclick="xlink('{.}','ctx');"><xsl:value-of select="./@title"/></a></div>
            </xsl:for-each>
            <div id="message" class="span5 ui-state-highlight ui-corner-all"></div>
          </div>
          <div class="row" id="ctx">
            <xsl:apply-templates select="page/content"/>
          </div>
        </div>
        <div class="copyright">Python Powered | &#169; 2012-2018 Hacker's Edge | <a href="http://www.pythondiary.com/">Blog</a></div>
      </body>
    </html>
  </xsl:template>

</xsl:stylesheet>
