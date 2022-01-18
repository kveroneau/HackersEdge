<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  
  <xsl:template match="span1">
    <div class="span1"><xsl:apply-templates/></div>
  </xsl:template>
  
  <xsl:template match="span9">
    <div class="span9">
      <div id="content" class="ui-widget-content ui-corner-all" style="overflow: auto;">
        <xsl:apply-templates/>
      </div>
    </div>
  </xsl:template>
  
  <xsl:template match="span12">
    <div class="span12">
      <div id="content" class="ui-widget-content ui-corner-all" style="overflow: auto;">
        <xsl:apply-templates/>
      </div>
    </div>
  </xsl:template>
  
  <xsl:template match="url">
    <a href="{.}"><xsl:value-of select="./@title"/></a>
  </xsl:template>
  
  <xsl:template match="mxml">
    <div class="mxml" data-xml="{xml}" data-xslt="{xslt}">Loading...</div>
  </xsl:template>
  
  <xsl:template match="a">
    <a href="#{@href}" onclick="xlink('{@href}','{@id}');"><xsl:value-of select="."/></a>
  </xsl:template>

  <xsl:template match="heading">
    <h2><xsl:value-of select="."/></h2>
  </xsl:template>
  
  <xsl:template match="p">
    <p><xsl:apply-templates/></p>
  </xsl:template>
  
  <xsl:template match="help">
    <strong><a href="/HelpCenter/{@topic}"><xsl:value-of select="."/></a></strong>
  </xsl:template>
  
  <xsl:template match="title">
    <script>document.title = "Hacker's Edge | <xsl:value-of select="."/>";</script>
  </xsl:template>
  
  <xsl:template match="vt100">
    <div id="vt100"></div>
    <strong>Feel like an elite hacker!</strong>  Play over telnet: hackers-edge.com:<xsl:value-of select="./@telnet"/><br/>
    <strong>You will need to <a href="#">create a character</a> before you can login here.</strong>
    <script>client = new HackersEdge('<xsl:value-of select="./@ws"/>');</script>
  </xsl:template>

  <xsl:template match="right">
    <div style="float: right;"><xsl:apply-templates/></div>
  </xsl:template>

  <xsl:template match="login">
    <script>
    dologin = function(){
      $.post("/accounts/login.xml", {'csrfmiddlewaretoken':'<xsl:value-of select="./@csrf"/>', 'username':$('#id_username').val(), 'password':$('#id_password').val()}, postok);
      return false;
    };
    </script>
    <form action="#/accounts/login.xml" method="post" onsubmit="return dologin();">
      <p><label for="id_username">Username:</label> <input id="id_username" maxlength="254" name="username" type="text"/></p>
      <p><label for="id_password">Password:</label> <input id="id_password" name="password" type="password"/></p>
      <input type="submit" value="Login" id="login_btn"/>
      <a href="/accounts/password/reset/">Forgot your password?</a>
    </form>
    <script>$("#login_btn").button();</script>
  </xsl:template>

  <xsl:template match="register">
    <a id="signup_btn" href="#/accounts/register.xml">Join today</a>
    <script>$("#signup_btn").button();</script>
  </xsl:template>

  <xsl:template match="signup">
    <script>
    dosignup = function(){
      $.post("/accounts/register.xml", {'csrfmiddlewaretoken':'<xsl:value-of select="./@csrf"/>', 'username':$('#id_username').val(), 'email':$('#id_email').val(), 'password1':$('#id_password1').val(), 'password2':$('#id_password2').val()}, postok);
      return false;
    };
    </script>
    <form action="#/accounts/register.xml" method="post" onsubmit="return dosignup();">
      <table>
      <tr><td><label for="id_username">Username:</label></td><td><input id="id_username" maxlength="254" name="username" type="text"/></td></tr>
      <tr><td><label for="id_email">E-mail:</label></td><td><input id="id_email" maxlength="254" name="email" type="email"/></td></tr>
      <tr><td><label for="id_password1">Password:</label></td><td><input id="id_password1" name="password1" type="password"/></td></tr>
      <tr><td><label for="id_password2">Password (again):</label></td><td><input id="id_password2" name="password2" type="password"/></td></tr>
      </table>
      <input type="submit" value="Sign up" id="signup_btn"/>
    </form>
    <script>$("#signup_btn").button();</script>
  </xsl:template>

  <xsl:template match="accordion">
    <div class="span3">
      <div id="accordion">
        <div class="mxml" data-xml="/accordion.xml" data-xslt="/s/xsl/nav.xsl">Loading...</div>
      </div>
    </div>
  </xsl:template>

  <xsl:template match="dialog">
    <div class="ui-widget">
    <div class="ui-widget-header ui-corner-top"><span class="ui-icon ui-icon-{title/@icon}" style="float:left;"></span><xsl:value-of select="title"/></div>
    <div class="ui-widget-content ui-corner-bottom">
    <xsl:apply-templates select="body"/>
    </div></div><br/>
  </xsl:template>
  
  <xsl:template match="button">
    <a class="btn" href="#{.}" onclick="return xlink('{.}', 'content');"><xsl:value-of select="@title"/></a>
  </xsl:template>
  
  <xsl:template match="characters">
    <table class="jtable" width="600">
      <thead><tr><th>Character</th><th>Host</th><th>Mailbox</th><th>Bank</th><th>Options</th></tr></thead>
      <tbody>
        <xsl:for-each select="character">
        <tr>
          <td><xsl:value-of select="."/></td>
          <td><xsl:value-of select="@ip_addr"/></td>
          <td><xsl:value-of select="@mailhost"/></td>
          <td><xsl:value-of select="@bank"/></td>
          <td>...</td>
        </tr>
        </xsl:for-each>
      </tbody>
    </table>
    <script>
      $(".jtable th").each(function(){ $(this).addClass("ui-state-default"); });
  $(".jtable td").each(function(){ $(this).addClass("ui-widget-content"); });
  $(".jtable tr").hover(function(){
   $(this).children("td").addClass("ui-state-hover");
  }, function(){
   $(this).children("td").removeClass("ui-state-hover");
  });
    </script>
  </xsl:template>

  <xsl:template match="form">
    <script>
    doform = function(){
      $.post("<xsl:value-of select="./@action"/>", {'csrfmiddlewaretoken':'<xsl:value-of select="./@csrf"/>',
      <xsl:for-each select="table/tr/td/input">
       '<xsl:value-of select="@name"/>':$('#<xsl:value-of select="@id"/>').val(),
      </xsl:for-each>
      <xsl:for-each select="table/tr/td/select">
       '<xsl:value-of select="@name"/>':$('#<xsl:value-of select="@id"/>').val(),
      </xsl:for-each>
      }, postok);
      return false;
    };
    </script>
    <form action="#{@action}" method="post" onsubmit="return doform();">
    <xsl:apply-templates select="table"/>
    <input type="submit" value="{./@button}" class="btn"/>
    <xsl:if test="@cancel">
      <a class="btn" style="float: right;" href="#{@cancel}" onclick="return xlink('{@cancel}', 'hash');">Cancel</a>
    </xsl:if>
    </form>
  </xsl:template>

  <xsl:template match="form/table">
    <table><xsl:apply-templates/></table>
  </xsl:template>
  
  <xsl:template match="form/table/tr">
    <tr><xsl:apply-templates/></tr>
  </xsl:template>
  
  <xsl:template match="form/table/tr/th/label">
    <th><xsl:value-of select="."/></th>
  </xsl:template>
  
  <xsl:template match="form/table/tr/td/input">
    <td><input id="{@id}" type="{@type}"/></td>
  </xsl:template>
  
  <xsl:template match="form/table/tr/td/select">
    <td><select id="{@id}">
    <xsl:for-each select="option">
      <option value="{@value}"><xsl:value-of select="."/></option>
    </xsl:for-each>
    </select></td>
  </xsl:template>

</xsl:stylesheet>
