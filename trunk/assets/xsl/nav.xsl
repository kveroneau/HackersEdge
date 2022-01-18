<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:template match="section">
    <h3><a href="#"><xsl:value-of select="@title"/></a></h3>
    <div>
      <xsl:for-each select="nav">
      <a href="#{.}" onclick="return xlink('{.}','{@id}');"><span class="ui-icon ui-icon-{@icon}" style="float:left;"></span><xsl:value-of select="@title"/></a><br/>
      </xsl:for-each>
    </div>
  </xsl:template>
</xsl:stylesheet>
