#-*- coding: utf-8 -*- 
from warnings import filterwarnings
from Crypto.Cipher import AES
from bs4 import BeautifulSoup
from pprint import pprint
import logging.handlers
import logging
import requests
import re, time
import os, json
import base64
import MySQLdb
import sys

class MySQLCommand(object):
    def __init__(self, host, port, user, passwd, db, table, logger):
        self.host = host
        self.port = port
        self.user = user
        self.password = passwd
        self.db = db
        self.table = table
        self.logger = logger
        filterwarnings('ignore', category = MySQLdb.Warning)

    def connectMysql(self):
        try:
            self.conn = MySQLdb.connect(host=self.host,port=self.port,user=self.user,passwd=self.password,db=self.db,charset='utf8')
            self.cursor = self.conn.cursor()
            self.createTable()
            return True
        except MySQLdb.Error,e:
            self.logger.info("Mysql Error %d: %s" % (e.args[0], e.args[1]))
            return False

    def createTable(self):
        sql = "CREATE TABLE IF NOT EXISTS songRap ("\
            "autoId INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,"\
            "songName VARCHAR(2048) NOT NULL,"\
            "songAuthor VARCHAR(2048) NOT NULL,"\
            "commentCount INT UNSIGNED NOT NULL DEFAULT 0,"\
            "style VARCHAR(2048) NOT NULL DEFAULT '',"\
            "hotAuthor VARCHAR(2048) NOT NULL DEFAULT '',"\
            "hotComment VARCHAR(2048) NOT NULL DEFAULT '',"\
            "hotLikedCount INT UNSIGNED NOT NULL DEFAULT 0"\
            ") ENGINE=InnoDB DEFAULT CHARSET=utf8"
        try:
            self.cursor.execute(sql)
        except MySQLdb.Error,e:
            self.logger.info("Mysql Error %d: %s" % (e.args[0], e.args[1]))

    def queryMysql(self, sql, param):
        try:
            self.cursor.execute(sql, param)
            row = self.cursor.fetchall()
            return row
        except MySQLdb.Error,e:
            self.logger.info("Mysql Error %d: %s" % (e.args[0], e.args[1]))
            return []

    def insertMysql(self, sql, param):
        try:
            self.cursor.execute(sql, param)
            #如果没有设置自动提交，需要主动提交
            self.conn.commit()
            self.logger.info(sql % param)
            return True
        except MySQLdb.Error,e:
            self.logger.info("Mysql Error %d: %s" % (e.args[0], e.args[1]))
            return False

    def updateMysql(self, sql):
        try:
            self.cursor.execute(sql)
            self.conn.commit()
            return True
        except MySQLdb.Error,e:
            self.logger.info("Mysql Error %d: %s" % (e.args[0], e.args[1]))
            self.conn.rollback()
            return False

    def closeMysql(self):
        self.cursor.close()
        self.conn.close()

class neteasySpider(object):
    def __init__(self, style, db, logger):
        self.style = style
        self.db = db
        self.logger = logger
        self.header = {
            'Cookie': 'appver=1.5.0.75771',
            'Referer': 'http://music.163.com',
        }
        self.session = requests.session()
        self.session.headers.update(self.header)
        self.session.keep_alive = False

    def aesEncrypt(self, text, secKey):
        pad = 16 - len(text) % 16
        text = text + pad * chr(pad)
        encryptor = AES.new(secKey, 2, '0102030405060708')
        ciphertext = encryptor.encrypt(text)
        ciphertext = base64.b64encode(ciphertext)
        return ciphertext


    def rsaEncrypt(self, text, pubKey, modulus):
        text = text[::-1]
        rs = int(text.encode('hex'), 16)**int(pubKey, 16) % int(modulus, 16)
        return format(rs, 'x').zfill(256)

    def createSecretKey(self, size):
        return (''.join(map(lambda xx: (hex(ord(xx))[2:]), os.urandom(size))))[0:16]

    def spiderGo(self, begin, end):
        for index in range(begin, end):
            self.getAllSongTableByIndex(index)

    def getAllSongTableByIndex(self, index):
        indexStr = '%d' % (int(index)*35)
        pageUrl = 'http://music.163.com/discover/playlist/?order=hot&cat=%s&limit=35&offset=%s' % (self.style, indexStr)
        self.logger.info("%s" % pageUrl)
        ret = self.session.get(pageUrl)
        soup = BeautifulSoup(ret.content, "html5lib")
        songList = soup.findAll('a', class_='icon-play f-fr')
        for item in songList:
            songId = item["data-res-id"]
            self.getPlaylistById(songId)

    def getPlaylistById(self, tableId):
        tableUrl = 'http://music.163.com/playlist?id=%s' % tableId
        ret = self.session.get(tableUrl)
        soup = BeautifulSoup(ret.content, "html5lib")
        songAll = soup.find('ul', class_='f-hide')
        songList = songAll.findAll('li')
        for i in songList:
            sName =  i.find('a').get_text()
            #sql = "select * from songEurope where songName='%s'" % self.db.escape_string(sName)
            sql = "select * from songRap where songName=%s"
            rows = self.db.queryMysql(sql, (sName,))
            if len(rows) != 0 :
                continue
            
            songUrl = (i.find('a'))['href']
            songId = songUrl.split('=')[1]
            self.getSongCommentById(songId)
    
    def getSongInfoById(self, songId):
        songUrl = 'http://music.163.com/song?id=%s' % songId
        ret = self.session.get(songUrl)
        soup = BeautifulSoup(ret.content, "html5lib")
        songDetail = soup.find('a', class_='u-btni u-btni-share ')
        if songDetail is None:
            return None

        songInfo = {
            "sAuthor":songDetail['data-res-author'],
            "sName":songDetail['data-res-name']
        }
        return songInfo

    def getSongCommentById(self, songId):
        url = 'http://music.163.com/weapi/v1/resource/comments/R_SO_4_%s?csrf_token=*******' % songId
        
        text = {
            'username': '**********',
            'password': '**********',
            'rememberLogin': 'true'
        }
        modulus = '00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7b725152b3ab17a876aea8a5aa76d2e417629ec4ee341f56135fccf695280104e0312ecbda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932575cce10b424d813cfe4875d3e82047b97ddef52741d546b8e289dc6935b3ece0462db0a22b8e7'
        nonce = '0CoJUm6Qyw8W8jud'
        pubKey = '010001'
        text = json.dumps(text)
        secKey = self.createSecretKey(16)
        encText = self.aesEncrypt(self.aesEncrypt(text, nonce), secKey)
        encSecKey = self.rsaEncrypt(secKey, pubKey, modulus)
        data = {
            'params': encText,
            'encSecKey': encSecKey
        }

        ret = self.session.post(url, headers=self.header, data=data)
        songInfo = self.getSongInfoById(songId)
        if songInfo is None:
            return

        totalNum = ret.json()['total']
        if int(totalNum) > 5000 or int(totalNum) < 800:
            return

        hotInfo = ret.json()['hotComments']
        hotAuthor = ""
        hotComment = ""
        hotLikedCount = "0"
        if len(hotInfo) > 0:
            hotAuthor = hotInfo[0]['user']['nickname']
            hotComment = hotInfo[0]['content']
            hotLikedCount = hotInfo[0]['likedCount']
        
        #######mysql#######
        sql = "insert into songRap(songName, songAuthor, commentCount, style, hotAuthor, hotComment, hotLikedCount) values(%s, %s, %s, %s, %s, %s, %s)"
        self.db.insertMysql(sql, (songInfo['sName'], songInfo['sAuthor'], str(totalNum), self.style, hotAuthor, hotComment, str(hotLikedCount)))

    def showDataFromMysql(self):
        pass

################GLOBAL###################
LOG_FILE = "logneteasy.log"
handler = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes = 1024*1024, backupCount = 5)
consoleHandler = logging.StreamHandler(sys.stdout)
fmt = '%(asctime)s - %(filename)s:%(lineno)s - %(message)s'
  
formatter = logging.Formatter(fmt)
handler.setFormatter(formatter)   
consoleHandler.setFormatter(formatter)
  
logger = logging.getLogger('wkw')    
logger.addHandler(handler)
logger.addHandler(consoleHandler)
logger.setLevel(logging.DEBUG)
##########################################

if __name__ == '__main__':
    reload(sys)
    sys.setdefaultencoding("utf-8")
    mysql = MySQLCommand("127.0.0.1", 3306, "root", "root", "neteasy", "songRap", logger)
    if mysql.connectMysql() == False:
        self.logger.info("Mysql Error:%s" % "error")
        exit()

    nt = neteasySpider('说唱', mysql, logger)
    nt.spiderGo(0, 15)
