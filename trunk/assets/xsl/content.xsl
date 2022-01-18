<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:import href="base.xsl"/>

  <xsl:template match="/">
    <script>document.title = "Hacker's Edge | <xsl:value-of select="{page//@title}"/>";</script>
    <xsl:apply-templates/>
  </xsl:template>

</xsl:stylesheet>
