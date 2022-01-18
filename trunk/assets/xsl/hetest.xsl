<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:template match="title">
    <script>document.title = "Hacker's Edge | <xsl:value-of select="."/>";</script>
  </xsl:template>

  <xsl:template match="hx">
    <div class="span12">
      <div id="content" class="ui-widget-content ui-corner-all" style="overflow: auto;">
        <h3><xsl:value-of select="."/></h3>
      </div>
    </div>
  </xsl:template>
</xsl:stylesheet>
