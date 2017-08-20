#coding:utf-8  
from email import encoders 
from email.header import Header
from email.mime.text import MIMEText 
from email.utils import parseaddr, formataddr
from email.MIMEImage import MIMEImage
from email.mime.multipart import MIMEMultipart
import smtplib
import urllib
import urllib2
import re
import sys
import requests
import logging
import logging.handlers
import logging
import MySQLdb
import time

class videoInfo :
    def __init__(self):
        self.author = ""
        self.name = ""
        self.uploadTime = ""
        self.picUrl = ""
        self.watchCount = ""

class MySQLCommand(object):
    def __init__(self,host,port,user,passwd,db,table,logger):
        self.host = host
        self.port = port
        self.user = user
        self.password = passwd
        self.db = db
        self.table = table
        self.logger = logger
    def connectMysql(self):
        try:
            self.conn = MySQLdb.connect(host=self.host,port=self.port,user=self.user,passwd=self.password,db=self.db,charset='utf8')
            self.cursor = self.conn.cursor()
            return True
        except MySQLdb.Error,e:
            self.logger.info("Mysql Error %d: %s" % (e.args[0], e.args[1]))
            return False
    def queryMysql(self, author, title):
        sql = "SELECT * FROM %s WHERE title='%s' AND author='%s'" % (self.table, title, author)
        try:
            self.cursor.execute(sql)
            row = self.cursor.fetchall()
            return row
        except:
            self.logger.info(sql + ' execute failed.')
            return []
    def insertMysql(self, author, title, watchCount):
        sql = "INSERT INTO %s (author, title, watchCount, time) VALUES('%s', '%s', '%s', '%s')" % (self.table, author, title, watchCount, time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time())))
        try:
            self.cursor.execute(sql)
            #如果没有设置自动提交，需要主动提交
            self.conn.commit()
            self.logger.info(sql)
            return True
        except:
            self.logger.info("%s insert failed." % sql)
            return False
    def updateMysqlSN(self, title, watchCount):
        sql = "UPDATE %s SET watchCount=%s WHERE title='%s'" % (self.table, watchCount, title)
        try:
            self.cursor.execute(sql)
            self.conn.commit()
            return True
        except:
            self.conn.rollback()
            return False
    def closeMysql(self):
        self.cursor.close()
        self.conn.close()

class Youtube :
    def __init__(self, url, db, logger):
        self.url = url
        self.logger = logger
        self.db = mysql
        self.check = {"min":"分鐘前", "hour":"小時前", "day":"天前"}
    def sendMail(self, debug, title, mailList, to_addr=['***'] ):
        from_addr= r'***'
        password = r'***'
        
        smtp_server = 'smtp.163.com' 

        msg = MIMEMultipart('related')
        msgAlternative = MIMEMultipart('alternative')
        msg.attach(msgAlternative)

        msgContent = ""

        send = []
        index = 1
        for idx in range(len(mailList)) :
            item = mailList[idx]
            rows = self.db.queryMysql(item.author, item.name)
            if len(rows) != 0 :
                continue
            #msgContent += '<h3>(%d): %s|%s|%s </h3><br><img src="cid:%d"><br>' % (idx+1, item.name, item.watchCount, item.uploadTime, idx)
            msgContent += '<h3>(%d): %s|%s|%s|%s </h3>' % (index, item.author, item.name, item.watchCount, item.uploadTime)
            send.append(item)
            index += 1

        if len(send) == 0 :
            self.logger.info("Send mail list already filter, origin mail list : %d, after list : %d", len(mailList), len(send))
            return
        self.logger.info("Begin send mail, len : %d", len(send))
        msgText = MIMEText(msgContent, 'html', 'utf-8')
        msgAlternative.attach(msgText)

        # for idx in range(len(mailList)) :
        #     item = mailList[idx]
        #     r = requests.get(item.picUrl)
        #     msgImage = MIMEImage(r.content)
        #     msgImage.add_header('Content-ID', '<%d>' % idx)
        #     msg.attach(msgImage)
        
        msg['From'] = from_addr
        msg['To'] = ','.join(to_addr)
        msg['Subject'] = title 
        try:
            server = smtplib.SMTP(smtp_server, 25)
            server.set_debuglevel(debug)
            server.login(from_addr, password)
            server.sendmail(from_addr,to_addr, msg.as_string())
            server.quit()
            self.logger.info("<%s> send success!!!" % title)
            for item in send:
                self.db.insertMysql(item.author, item.name, item.watchCount)
        except Exception as e :
            logger.info("Error: Send mail failed <%s> with %s" % (title, str(e)))

    def dowloadPic(self, imageUrl, filePath):
        r = requests.get(imageUrl)
        with open(filePath, "wb") as code:
            code.write(r.content)
    
    def reqYoutubeAll(self):
        mailList = []
        title = ""
        for key in self.url:
            author = key
            subList = self.reqYoutube(author, self.url[key])
            if len(subList) > 0:
                title = "%s" % (author)
                mailList.extend(subList)
        if len(mailList) > 0 :
            self.sendMail(0, title, mailList)

    def reqYoutube(self, author, url):
        user_agent = 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'    
        
        headers = { 'User-Agent' : user_agent }    
        session = requests.session()
    	ret = session.get(url, headers=header)
        the_page = ret.content

        #视频截图
        # <span class="yt-thumb-default">
        #   <span class="yt-thumb-clip">
        #         <img src="https://i.ytimg.com/vi/QsBJXVmKklU/hqdefault.jpg?sqp=-oaymwEWCMQBEG5IWvKriqkDCQgBFQAAiEIYAQ==&amp;rs=AOn4CLDo5RbiHzWEqSpTciB_E5sNa9wHrw" aria-hidden="true" alt="" data-ytimg="1" onload=";window.__ytRIL &amp;&amp; __ytRIL(this)" width="196" >
        #     <span class="vertical-align"></span>
        #   </span>
        # </span>
        #re.DOTALL 匹配换行符
        infoList = []
        result0 = re.findall(r'<span class="yt-thumb-default">(.*?)<span class="yt-thumb-clip">(.*?)<img(.*?)src=(.*?)>(.*?)<span class="vertical-align"></span>', the_page, re.S|re.M|re.DOTALL)
        for item in result0:
            entry = videoInfo()
            entry.picUrl = item[3].encode('utf-8').split("\"", 3)[1].replace("amp;","")
            #print(item[3].encode('utf-8').split("\"", 3)[1].replace("amp;",""))
            infoList.append(entry)
        
        #视频标题时间
        result1 = re.findall(r'<h3 class="yt-lockup-title ">(.*?)title=(.*?)aria-describedby=(.*?)</h3>', the_page, re.S|re.M)
        index = 0
        for item in result1:
            infoList[index].author = author
            infoList[index].name = item[1].encode('utf-8').replace("\"", "").split("-", 2)[0]
            index += 1

        #观看次数
        result2 = re.findall(r'<li>觀看(.*?)</li><li>(.*?)</li>', the_page, re.S|re.M)
        index = 0
        for item in result2:
            #print("%s, %s" % (item[0].encode('utf-8'), item[1].encode('utf-8')))
            infoList[index].watchCount = item[0].encode('utf-8').split("：", 2)[1]
            infoList[index].uploadTime = item[1].encode('utf-8')
            index += 1
        
        mailList = []
        for item in infoList :
            #27 分鐘前"1 分鐘前" "1 小時前"  or item.uploadTime == "3 天前"
            check = item.uploadTime.split(" ", 2)[1]
            if check != self.check["min"]:
                continue

            mailList.append(item)
            logger.info("%s, %s, %s" % (item.uploadTime, item.watchCount, item.name))

        logger.info("mailList : %d" % len(mailList))
        return mailList

################GLOBAL###################
LOG_FILE = "youtube.log"
handler = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes = 1024*1024, backupCount = 5)
fmt = '%(asctime)s - %(filename)s:%(lineno)s - %(message)s'
  
formatter = logging.Formatter(fmt)
handler.setFormatter(formatter)   
  
logger = logging.getLogger('tst')    
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)
##########################################

if __name__== '__main__':
    reload(sys)
    sys.setdefaultencoding("utf-8")
    ###### Mysql #######
    mysql = MySQLCommand("127.0.0.1", 3306, "root", "root", "youtube", "youtube", logger)
    if mysql.connectMysql() == False:
        exit()
    ####################
    url = {
        "basketball&more":"https://www.youtube.com/channel/UCMsEVuICS3t9B0bGVWstYwQ/videos", 
        "BdotAdot5":"https://www.youtube.com/user/BdotAdot5/videos"
    }
    ytb = Youtube(url, mysql, logger)
    ytb.reqYoutubeAll()
    ####################
    mysql.closeMysql()
