#!/usr/local/bin/python3

import re
import os
import pickle
#import ads.sandbox as ads
import ads
import codecs
import time
import sys
import matplotlib
#matplotlib.use('TkAgg')
import matplotlib.pyplot as pl
import numpy as np
#import pylab as pl
import datetime as dt
import argparse as ap
from shutil import copyfile
from operator import itemgetter

'''
Read huibl data file, for maintaining publications, web side and monitor citations
v19 cleaned up some reporting new citations, purge multiple entries on same day
- note wrote a cleanup routine to delete redundant citation entries.
todo
- v9: check 4 cits, check excel
-v10: also compare to last run
- check -1 counts for sources with temp arXiV
- Because the arXiv counts make the citations go up and down, it is alos useful to have a csv of the last run and 
    compare new citations against the last run. Otherwise the count going down can mas a new citation
 - write docx?
 - enter new switch to write bibcode/stats for papers with specific co-author 
 
 - writes a csv file with co-authored papers
 - which can then be used for plotting. Plot tags are taken form intermediary file
 
'''
rootdir = os.environ['HOME']

monthdir = rootdir+'/Work/Docs/Huib/Publists'
dailydir = rootdir+'/Work/Mondata/Huibl'
dostatsupdate = False
verbose = False
debug = False
Nadspol = 0
#doAdsPol = False
#exAdsPol = ['2017ApJ...848L..12A']
#maxpolads = 500
if debug: print('Counting:',Nadspol)
sorttype = ['paper','confer','book','popular','poster','memo','other']
pubencoding = 'utf-8'
version = 'v3'

arroot = rootdir+'/Work/Web/Live/Archive'
arref = 'Archive'

def GetArgs():
    '''
    Get the arguments to reading the data
    '''
    parser = ap.ArgumentParser(description='Update list of publications & citations')
    #    parser.add_argument('integers', metavar='N', type=int, nargs='+',
    #               help='an integer for the accumulator')
    parser.add_argument('-n','--noupdate', action = 'store_true',
                   help='do not update from ads')
    parser.add_argument('-c','--compare', choices=['month','recent','day'],
                        default = 'month',
                        help='compare to monthly savings or most recent (yesterday?)')
    parser.add_argument('-y','--yscale', choices=['linear','log','root'],
                        default = 'linear',
                        help ='scale on y axis, lin, log or root')
    parser.add_argument('-p','--plot', choices=['papsel','citsum','allpap','hindex','hinnow','none'],
                        default = 'none',
                        help='plot todo, papsel, citsum, allpap, hindex,none')
    parser.add_argument('-w','--window', choices=['all','adecade','a5year','a4year','a3year','ayear','amonth','aweek'],
                        default = 'all',
                        help='plot window constrained to last ...')
    parser.add_argument('-s','--sort', choices=['original','reverse','byyear','bycits',
                        'typeyear','typecits'], default = 'reverse',
                        help='sort order for html output')
    parser.add_argument('-x','--maxpolads',type=int,default=500)
    parser.add_argument('-a','--coauth',type=str,default='')
    parser.add_argument('-f','--bibfile',type=str,default='')

    args = parser.parse_args()
    return args


class CitStats():

    class CitPaper():
        def __init__(self,bib='',author='',tag='',type='memo',cits=[]):
            self.bib=bib
            self.ids={}
            self.ids['author']=author
            self.ids['tag']=tag
            self.ids['type']=type
            self.cits=cits

    def __init__(self, papers=None,dates=None):
        if (papers == None): papers = []
        if (dates == None): dates = []
        self.fields=['author','tag','type']
        self.papers = papers
        self.dates = dates
        return
    def dtDates(self):
        dtdates = []
        for date in self.dates:
            tmp = date.split('/')
            year = int(tmp[2])
            #print('y e a r:',year)
            if (year < 1000):
                if (year > 50 ): year += 1900
                else: year += 2000
            dtdates.append(dt.datetime(year,int(tmp[1]),int(tmp[0])))
        return dtdates
    def dump(self,output):
        #write header
        output.write('{:20}'.format('Header'))
        for field in self.fields:
            output.write('{:20}'.format(field))
        for day in self.dates:
            output.write('{:8}'.format(day))
        output.write('\n')
        for pap in self.papers:
            output.write('{:20}'.format(pap.bib))
            for field in self.fields:
                output.write('{:20}'.format(pap.ids[field]))
            for count in pap.cits:
                output.write('{:8}'.format(count))
            output.write('\n')
    def addPaper(self,paper,author,tag,type,newcit):
        #add a paper, set cits to zero, but most recent to newcit
        tmpcits = []
        for day in range(len(self.dates)-1):
            tmpcits.append(0)
        tmpcits.append(newcit)        
        self.papers.append(self.CitPaper(paper,author,tag,type,tmpcits))
    def delCol(self,id):
        del self.dates[id]
        for pap in self.papers:
            del pap.cits[id]
        return
    def addDate(self,date):
        self.dates.append(date)
        for pap in self.papers:
                pap.cits.append(-1)
    def updCits(self, code, newc ):
        #updates the most recent cit
        for pap in self.papers:
            if (pap.bib == code):
                pap.cits[-1] = newc
    def readStats(self,file):
        stafile = open(file,'r',encoding='ascii')
        readheader = True
        for line in stafile:
            fields = line.rstrip('\r\n').split(',')
            ncols = len(fields)
            if (readheader):
                for i in range(len(self.fields)):
                    #print('Test:',i,fields[0],fields[1])
                    if ( fields[i+1] != self.fields[i] ): print('WARN fields',i, fields, self.fields)
                for i in range(len(self.fields)+1,ncols):
                    self.dates.append(fields[i])
                readheader = False
            else:
                tmpcits = []
                for i in range(len(self.fields)+1,ncols):
                    #print('debug:',i,fields[i])
                    tmpcits.append(int(fields[i]))
                self.papers.append(self.CitPaper(fields[0],fields[1],fields[2],fields[3],tmpcits))

    def writeStats(self,file):
        #first check whether the new column has same date as one but last
        if (self.dates[-1] == self.dates[-2]):
            print('Rerunning on ',self.dates[-2],' cleaning up')
            self.delCol(-2)
    
        outp = open(file,'w',encoding='ascii',errors='ignore')
        outp.write('{},'.format('bibcode'))
        for field in self.fields:
            outp.write('{},'.format(field))
        for entry in self.dates[:-1]:
            outp.write('{},'.format(entry))
        outp.write('{}\n'.format(self.dates[-1]))
        #for pap in self.papers:
        for pap in sorted(self.papers, key = lambda num: num.cits[-1], reverse=True):
            #for cit in sorted(cits, key = lambda numb: numb[-1], reverse=True ):
            outp.write('{},'.format(pap.bib))
            for id in self.fields:
                #print('debug',pap.ids[id])
                outp.write('{},'.format((pap.ids[id])))
            for cit in pap.cits[:-1]:
                outp.write('{},'.format(cit))
            outp.write('{}\n'.format(pap.cits[-1]))
    def mostRecent(self):
        return self.dates[-1]

    def reportGrads(self, top):
        x = self.dtDates()
        #print('Top:',top,len(x))
        for pap in self.papers:
            if (pap.bib == top):
                firstd = x[-1]
                Found = False
                idate = 0
                while (not Found and idate<len(pap.cits)-1):
                    if (pap.cits[idate] > 0):
                        Found = True
                        firstd = x[idate]
                    idate+=1
                if (pap.cits[-1]==0): 
                    grad=0
                else:
                    grad = pap.cits[-1]/(float((x[-1]-firstd).days))
        print('Grad:',top,firstd,grad*365.)

    def extrPlots(self, top):
        #return dates, scores and tag for top bibcode, for plor
        x = self.dtDates()
        y = []
        name = ''
        for pap in self.papers:
            if (pap.bib == top):
                y = pap.cits
                name = pap.bib+':'+pap.ids['author']+' ('+pap.ids['tag']+')'
        return name, x, y
    def sumPlots(self):
        x = self.dtDates()
        y = []
        for idt in range(len(self.dates)):
            sumcit = 0
            for pap in self.papers:
                sumcit += pap.cits[idt]
            y.append(sumcit)
        return 'Sum Citations',x,y
    def indexH(self):
        x = self.dtDates()
        y = []
        hinnow = []
        for idt in range(len(self.dates)):
            tmph = []
            #print 'rset',tmph
            for pap in self.papers:
                tmph.append(pap.cits[idt])
                #print idt,pap.bib,pap.cits[idt]
            tmph.sort(reverse = True)
            #print '1 dim',tmph
            hindex = 0
            #print 'hin on date', idt, tmph
            if(idt == len(self.dates)-1):
                hinnow = tmph
            for ih in range(len(tmph)):
                if (ih+1 <= tmph[ih]):
                    #print('Ha:',ih,ih+1,tmph[ih])
                    hindex = ih+1
            y.append(hindex)
        
        print('Current H index: ',y[-1])
        #huib hier
        best = 0
        for pap in self.papers:
            #print the nearest paper to increase H and those within 3
            if (pap.cits[-1] <= y[-1] and pap.cits[-1] > best):
                best = pap.cits[-1]
        for pap in self.papers:
            if (pap.cits[-1] <= y[-1] and (best - pap.cits[-1]) < 3):
                print('Close to increase Hindex: {:19}, {:20} at {:3}'.format(
                pap.bib, pap.ids['author'],pap.cits[-1]))
        return 'H index',x,y, hinnow
    def findSteepest(self,deltad,exclude):
        '''return the steepest riser in deltad, taking into account exclude'''
        recedate = self.dtDates()[-1]
        ilast = 0
        idt = 0
        for dtdate in self.dtDates():
            if (recedate-dtdate>dt.timedelta(deltad)):
                ilast = idt
            idt += 1
        steeppap = self.papers[0]
        steepest = 0
        for pap in self.papers:
            if ((pap.cits[-1]-pap.cits[ilast])>steepest and pap.bib not in exclude ):
                steeppap = pap
                steepest = pap.cits[-1]-pap.cits[ilast]
        print('Steepest riser over {:6.2f} yr: {:19}, {:20} from {:3} to {:3}'.format(deltad/365,
            steeppap.bib, steeppap.ids['author'],steeppap.cits[ilast],steeppap.cits[-1]))
        return steeppap.bib
    def allCodes(self):
        #all papers with a cit
        mypapers = []
        for pap in self.papers:
            if (pap.cits[-1] > 0):
                mypapers.append(pap.bib)
        return mypapers
      
    def selBibCodes(self):
        '''
        print som<e articles with interesting stats
        and return a list of fav articles for plotting 
        '''
        minimal = ['2006ASPC..351..497K','1995ApJ...448L.123V','2017ApJ...834L...8M']
        exclude = ['2017ApJ...848L..12A','2017Natur.541...58C','2017ApJ...834L...7T']
        for code in minimal:
            for pap in self.papers:
                if (pap.bib == code):
                    print('Favourite paper  : {:19}, {:20} now at {:3}'.format(pap.bib, 
                        pap.ids['author'],pap.cits[-1]))
        for code in exclude:
            for pap in self.papers:
                if (pap.bib == code):
                    print('Exlude from stats: {:19}, {:20} now at {:3}'.format(pap.bib, 
                        pap.ids['author'],pap.cits[-1]))
        #find most cited
        maxcit = 0
        maxpap = self.papers[0]
        for pap in self.papers:
            if (pap.cits[-1] > maxcit and pap.bib not in exclude):
                maxcit = pap.cits[-1]
                maxpap = pap
        print('Max cited paper: {:19}, {:20} now at {:3}'.format(maxpap.bib, 
                    maxpap.ids['author'],maxpap.cits[-1]))  
        #maintain a list with papers to plot:
        plotlist = minimal      
        if (not maxpap.bib in plotlist): plotlist.append(maxpap.bib)
        #find fastest increase
        steeppap = self.findSteepest(16*365,exclude)
        if (not steeppap in plotlist): plotlist.append(steeppap)                     
        steeppap = self.findSteepest(4*365,exclude)
        if (not steeppap in plotlist): plotlist.append(steeppap)                     
        steeppap = self.findSteepest(365,exclude)
        if (not steeppap in plotlist): plotlist.append(steeppap)                     
        steeppap = self.findSteepest(0.25*365,exclude)
        if (not steeppap in plotlist): plotlist.append(steeppap)                             
        #find all first author with more than 20
        for pap in self.papers:
            if (pap.cits[-1] > 35 and (pap.ids['author'].find('angeveld')>0)):
                if (not pap.bib in plotlist): plotlist.append(pap.bib)                     
        return plotlist
        
    def reportCits(self, pltype, plwindow, yscale, biblist, plttags ):
        '''
        Generate report on citations by plotting
        '''
        def plotHinnow(hinnow):
        
            x = np.array(range(len(hinnow)))+1
            hsel = np.where( x < hinnow )
            ih=hsel[0][-1]

            #print('paper:',papcits['pap'][ih],' has:',papcits['cits'][ih])
            #print('paper:',papcits['pap'][ih+1],' has:',papcits['cits'][ih+1])
            hindex=x[ih]

            x1, y1 = [hindex, 0], [hindex, hindex]
            x2, y2 = [hindex, hindex], [0, hindex]
            pl.plot(x1, y1, x2, y2,'k-')
            pl.plot(x,hinnow)
            pl.yscale('log')
            pl.show()
        
        def plotCits( taglist, xlistx, ylisty, xmin, ymin, yscale ):
            print ('yscale:',yscale)
            myscale = 'linear'
            if (yscale=='log'): myscale= 'log'
            
            #print('>1>',type(xlistx),type(ylisty),type(xlistx[0]),type(ylisty[0]),type(xlistx[0][0]),type(ylisty[0][0]),xlistx[0][0])
            x = np.array(xlistx,dtype=dt.datetime)
            #for lll in ylisty:
            #    print('>>>>>',len(lll),lll[0])
            y = np.array(ylisty,dtype='int')
            mycol=['r','g','b','k','m',
                   'darkcyan','orange','maroon',
                   'navy','teal', 'gray', 'purple'] #omitting 'y' and 'w'
            pl.title("citation tracking")
            pl.ylabel('citations')
            pl.xlabel('date')
            #print('>2>',type(x),x.shape,type(y),y.shape)
            #for xval in 
            #print('>3>',x,xmin)
            #tmpmin = x - xmin
            #print('>4>',type(x[0]),type(x[0][0]),type(xmin))
            ibeg = (abs(x - xmin)).argmin()
            #print('>5>',ibeg,x[1][-1],xmin)
            pl.xlim(right=x[0][-1],left=xmin)
            print('shape:',y.shape)
            pl.ylim(bottom=max(1,0.99*np.min(y[:,ibeg:-1])), top=1.01*np.max(y[:,ibeg:-1]))
            print('YLim:',np.min(y[:,ibeg:-1]),np.max(y[:,ibeg:-1]))
            ic = 0
            for ipl in range(len(x)):
                pl.plot(x[ipl],y[ipl],c=mycol[ic],lw=2,label=taglist[ipl])
                ic += 1
                if (ic > len(mycol)-1): ic = 0
            ax = pl.subplot(111)
            ax.set_yscale(myscale)
            box = ax.get_position()
            ax.set_position([box.x0-0.1*box.width, box.y0 + box.height * 0.2,
                         1.2*box.width, box.height * 0.8])
            ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.07), ncol=4, fontsize=8)

            #wm = pl.get_current_fig_manager()
            #wm.window.wm_geometry("1400x400+5+5")
            pl.show()  
    
        x = []
        y = []
        tag = []
        sumtag,sumx,sumy = self.sumPlots()
        hixtag,hix,hiy,hinnow = self.indexH()
        if (len(biblist)==0):    
            biblist = self.selBibCodes()
        
        if( pltype == 'hinnow' ):
            plotHinnow(hinnow)
        
        elif (pltype == 'papsel'):
            for ib, art in enumerate(biblist):
                #print('Loop:',art,ib)
                tmptag,tmpx,tmpy = self.extrPlots(art)
                #These arre the tags from the big csv files
                #print('Tmp tag:',tmptag,len(tmpx),len(tmpy))
                self.reportGrads(art)
                if (len(plttags)==0):
                    tag.append(tmptag)
                else:
                    tag.append(plttags[ib])
                x.append(tmpx)
                y.append(tmpy)
        elif (pltype == 'citsum'):
            x.append(sumx)
            y.append(sumy)
            tag.append(sumtag)
        elif (pltype == 'hindex'):
             x.append(hix)
             y.append(hiy)
             tag.append(hixtag)
        elif (pltype == 'allpap'):
            biblist = self.allCodes()
            for art in biblist:
                tmptag,tmpx,tmpy = self.extrPlots(art)
                tag.append(tmptag)
                x.append(tmpx)
                y.append(tmpy)
        elif (pltype == 'none'):
            pass
        else:
            print('Unknown plot type:',pltype)
        if (len(x)>0):
            xmin = x[0][0]
            if (plwindow != 'all'):
                if (plwindow=='adecade'): deltaday = 3653
                if (plwindow=='a5year'): deltaday = 1826
                if (plwindow=='a4year'): deltaday = 1520 #should be 1460
                if (plwindow=='a3year'): deltaday = 1095                
                if (plwindow=='ayear'): deltaday = 365
                if (plwindow=='amonth'): deltaday = 30
                if (plwindow=='aweek'): deltaday = 7
                xmin = dt.datetime.now() - dt.timedelta(deltaday) 
            ymin = 5000       
            plotCits( tag, x, y, xmin, ymin, yscale )
        return    

class Paper():
    '''Local storage class for papers'''
    def __init__(self,bibcode='.'*19,tag='notag',year='0000',authors=[],
                    pubmag='unknown',pubpag=0,pubvol=0, matched=False):
        self.bibcode = bibcode
        self.tag = tag
        self.year = year
        self.authors = authors
        self.pubmag = pubmag
        self.pubvol = pubvol
        self.pubpag = pubpag
        self.pubful = 'Somewhere'
        self.cits = -1
        self.citlist = []
        self.oldcits = -1
        self.type = ''
        self.files = []
        self.actions = []
        self.links = []
        self.comments = []
        self.altbibcodes = []
        self.matched = False
    def __lt__(self,pap2):
        return str(self.bibcode)<str(pap2.bibcode)

    def strSum(self):
        firsta = self.authors[0].split(',')[0]
        outstr = '{:16}: {:19} ({:20})'.format(firsta,self.bibcode,self.tag)
        #print self.bibcode, self.tag, self.year, self.authors[0]
        return outstr

    def PubHtml(self,output):
        #print('debug:','<LI>{}'.format(self.authors[0]).encode('ascii', 'xmlcharrefreplace'))
        #print('debug:',u'<LI>{}'.format(self.authors[0]))
        output.write(u'<LI>{}'.format(self.authors[0]))
        if (len(self.authors)>25):
            huib = ''
            for name in self.authors:
                if (name.find('angeveld')>0):
                    huib = name
            for name in self.authors[1:4]:
                output.write('; {}'.format(name))
            output.write(', and {} authors including {},'.format((len(self.authors)-4), huib))    
        else:
            for name in self.authors[1:]:
                output.write('; {}'.format(name))
        output.write('\n')
        output.write('<CITE>"{}"</CITE>,\n'.format(self.title))
        output.write('{}, {}<BR>\n'.format(self.year,self.pubful))
        for link in self.files:
            rlink = arref+'/'+link
            output.write('<A HREF={}> PDF file</A> availabe.\n'.format(rlink))
        output.write('<P>\n\n')

    def Full(self,output):
        '''Print in same format v3'''
        output.write('HuiBl-v3: {}, {}, {}\n'.format(self.bibcode, self.tag, self.type))
        for name in self.authors:
            if (name == self.authors[-1]):
                output.write('{};\n'.format(name))
            else:
                output.write('{}; '.format(name))
        output.write('"{}"\n'.format(self.title))

        if (self.type != 'paper' or self.pubmag == 'unknown'):
            output.write('{}, {}\n'.format(self.year, self.pubful))
        else:
            if hasattr( self, 'pubspecial'):
                output.write('{}, {} ({}) {}, {}\n'.format(self.year, self.pubmag, self.pubspecial, self.pubvol, self.pubpag))
            else:
                output.write('{}, {} {}, {}\n'.format(self.year, self.pubmag, self.pubvol, self.pubpag))
        for pub in self.files:
            output.write('file: {}\n'.format(pub))
        if hasattr( self, 'preprint'):
            output.write('preprint: {}\n'.format(self.preprint))
        for reas in self.comments:
            output.write('#{}\n'.format(reas))
        for code in self.altbibcodes:
            output.write('altbibcode: {}\n'.format(code))
        for date in self.actions:
            output.write('{} {}\n'.format(date[0],date[1]))
        for url in self.links:
            output.write('link: {}\n'.format(url))
            
    def ParsePub(self, line):
        '''Parse publication line, once needed for finding bib code v3'''
        repubarxiv = re.compile(r'^\d{4}\,?\s+(arXiv)\:(\d{4})\.(\d{3,5})')
        repubart = re.compile(r'^\d{4}\,?\s+(\S+\_?\S)\,?\s+(\d{1,6})\,?\s+(A|L|P)?(\d{1,6})')
        respecial = re.compile(r'^\d{4}\,?\s+(\S+)\,?\s+\((.+)\)\s+(\d{1,6})\,?\s+(A|L|P)?(\d{1,6})')
        #reproc = re.compile(r'^\d{4}\,?\s+(?:in\s*)(?:the\s*)?Proceedings\ of\s+(\".*\")\,?\s*(.*)\,?\s+p?\.?\s*(\d{1,4})\s*(\-\s*\d{1,4})?\s*$')
        matchpubart = repubart.match(line)
        matchspecial = respecial.match(line)
        matcharxiv = repubarxiv.match(line)
        #matchproc = reproc.match(line)
        #print '>>',line
        if (matchpubart):
            self.pubmag =matchpubart.group(1)
            self.pubvol =matchpubart.group(2)
            self.pubpag =matchpubart.group(4)
            #self.GenBibcode()
            return True
        elif matchspecial:
        #1989, A&A (Letters) 216 L1-L4
            self.pubmag =matchspecial.group(1)
            self.pubspecial = matchspecial.group(2)
            self.pubvol =matchspecial.group(3)
            self.pubpag =matchspecial.group(5)
            #self.GenBibcode()
            return True
        elif matcharxiv:
            self.pubmag =matcharxiv.group(1)
            self.pubvol =matcharxiv.group(2)
            self.pubpag =matcharxiv.group(3)
        else:
            if verbose: print('WARN: Decoding v3 data, pubs not recognised: {}'.format(line))
            return False

    def GenBibcode(self):
        self.pubmag = self.pubmag.rstrip(',')
        self.bibcode = self.year+self.pubmag
        pad = '.'*(5-len(self.pubmag)+4-len(self.pubvol))
        self.bibcode += pad + self.pubvol
        if hasattr(self, 'pubspecial'):
            self.bibcode += self.pubspecial[0]
        else:
            self.bibcode += '.'
        pad = '.'*(4-len(self.pubpag))
        self.bibcode += pad + self.pubpag + self.authors[0][0].upper()
        
    def __setitem__(self,key,value):
        self.__dict__[key] = value
        
    def fillFromAds(self, ads):
        self.bibcode = ads.bibcode
        self.authors = ads.author
        self.year = ads.year
        self.title = ads.title[0]
        #Trying this Huib, some papers have not resolved this v13
        try:
            self.pubful = '{} {}, {}'.format(ads.pub, ads.volume, ads.page[0])        
            tmpdate = str(ads.pubdate)
            adsdate = tmpdate[8:10]+tmpdate[5:7]+tmpdate[2:4]
            self.actions.append((adsdate,'adsdate'))
        except:
            pass
            
    def UpdateByADS(self, ads):
        '''deprecated for now'''
        self.authors = ads.author
        self.title = ads.title[0]
        #print ads.pubdate, type(ads.pubdate)
        try:
            tmpdate = str(ads.pubdate)
            adsdate = tmpdate[8:10]+tmpdate[5:7]+tmpdate[2:4]
            self.actions.append((adsdate,'adsdate'))
        except:
            pass

class ListPapers():
    def __init__(self):
        self.list = []
    def Insert(self,paper=Paper()):
        self.list.append(paper)
    def SumList(self):
        for paper in self.list:
            print('Sum:',paper.strSum())
    def FullList(self, outfile, mycoding):
        output = open(outfile,'w', encoding = mycoding)
        for paper in self.list:
            output.write('\n')
            paper.Full(output)
    def getCits(self,item):
        return self.list[item].cits
    def addStats(self, stats):
        for paper in self.list:
            for citpap in stats.papers:
                if ( paper.bibcode == citpap.bib ):
                    paper.oldcits = citpap.cits[-1]
                    paper.cits = paper.oldcits
    def SelCoAuth(self, coauth):
        biblist = []
        for paper in self.list:
            for auth in paper.authors:
                if (coauth in auth):
                    biblist.append(paper.bibcode)
        return biblist

    def ReadPubV3(self,file, myencoding ):
        '''parsing v3 file and filling list of papers'''
        v3lines = {
            'comment': re.compile(r'^\#(.*)'),
            'header': re.compile(r'^HuiBl-v3:\s(.{19})\,\s*(\S+),\s*(\S+)\s*(.*)?\s*$'),
            'author': re.compile(r'^((.*)\,\s*(.*)\;)+$'),
            'title': re.compile(r'^\"(.*)\"\s*$'),
            'pub': re.compile(r'^(\d{4})\,?\s+(.*)$'),
            'action': re.compile(r'^(\d{6})\s+((in\s)?\S+)\s*(\S*)?\s*$'),
            'file': re.compile(r'^file\:\s*(\S+\.\w+)\s*$'),
            'altbibcode' : re.compile(r'altbibcode\:\s*(\S*)\s*$'),
            'preprint' : re.compile(r'preprint\:\s*(\S*)\s*$'),
            'link': re.compile(r'^link\:\s*(http\S+)\s*$'),
            'blank': re.compile(r'^\s*$') }
                    
        datain = open(file,'r', encoding = myencoding)
        inblock = False
        nwarn = 0
        nhead = 0
        for line in datain:
            line = line.rstrip('\n')
            if debug: print(line)
            foundmatch = False
            for ltype in list(v3lines.keys()):
                #print ltype, oldlines[ltype]
                match = v3lines[ltype].match(line)
                #first determine if in block
                if (match):
                    #print ltype,':',line
                    foundmatch = True
                    if (ltype == 'blank'):
                        inblock == False  
                    elif (ltype == 'header'):
                        inblock = True                                        
                if (match and inblock):
                    #time to modify data 
                    if (ltype == 'header'):
                        nhead += 1
                        curpap = Paper(bibcode=match.group(1))
                        self.Insert(curpap)
                        curpap.tag = match.group(2)
                        curpap.type =match.group(3)
                    elif (ltype == 'comment'):
                        curpap.comments.append(match.group(1))
                    elif (ltype == 'altbibcode'):
                        curpap.altbibcodes.append(match.group(1))
                    elif (ltype == 'preprint'):
                        curpap.preprint = match.group(1)
                    elif (ltype == 'author'):
                        curpap.authors = line.rstrip(';').split('; ')
                    elif ( ltype == 'title'):
                        curpap.title =match.group(1)
                    elif ( ltype == 'pub' ):
                        curpap.year = match.group(1)
                        curpap.pubful = match.group(2)
                        if (curpap.type == 'paper'):
                            curpap.ParsePub(line)
                    elif ( ltype == 'file' ):
                        curpap.files.append(match.group(1))
                    elif ( ltype == 'link' ):
                        curpap.links.append(match.group(1))
                    elif ( ltype == 'action' ):
                        curpap.actions.append((match.group(1),match.group(2)))                    
                elif (match and not inblock):
                    if (ltype == 'comment' ):
                        if verbose: print('#{}'.format(match.group(1)))
                    elif (ltype == 'blank'):
                        pass
                    else:
                        if verbose: print('WARN: unexpected line of type {}: {}'.format(ltype,line))
                        nwarn += 1
            if ( not foundmatch):
                inblock = False
                if verbose: print('WARN: unmatched line: {}'.format(line))
                nwarn += 1
        print('Read {} headers, {} unexpected lines'.format(nhead,nwarn))
        
    def checkFiles(self):
    
        stats = {}
        for type in sorttype:
            stats[type] = {'nent':0, 'nhas':0, 'nlnk':0, 'nps':0}
    
        for pap in self.list:
            #papers should have links
            if (len(pap.files)<1 and pap.type == 'paper'):
                print('WARN, no file for {}'.format(pap.strSum()))
            #all files should exist
            for link in pap.files:
                linkf = arroot+'/'+link
                if (not os.path.isfile(linkf)):
                    print('WARN cannot find {}!'.format(link))
            #add stats
            stats[pap.type]['nent'] +=1
            if (len(pap.files) > 0): stats[pap.type]['nhas'] += 1
            stats[pap.type]['nlnk'] += len(pap.files)
            for link in pap.files:
                if (link.find('.ps') >0 ):
                    stats[pap.type]['nps'] +=1
        for type in sorttype:
            print('type {:8}, total {:3}, with file {:3}, total files {:3}, {:3} ps ext'.format(
                type,stats[type]['nent'],stats[type]['nhas'],stats[type]['nlnk'],stats[type]['nps']))
                

        
    def writeHtml(self, sort, dir, outroot):
        if debug: print('debug, sort is:',sort)
        htmlout = open(dir+'/'+outroot+'.html','w',encoding='ascii',errors='xmlcharrefreplace')
        print('Writing:'+dir+'/'+outroot+'.html')
        htmlout.write('<CITE>Last updated: {}</CITE><BR>\n<OL>\n'.format(dt.datetime.now().strftime("%a %d/%m/%Y %H:%M %Z")))
        
        if (sort == 'typeyear'):
            for pap in sorted(self.list, key =lambda x: (-1*sorttype.index(x.type), x.year), reverse=(True) ):
                pap.PubHtml(htmlout)
        elif (sort == 'typecits'):
            for pap in sorted(self.list, key =lambda x: (-1*sorttype.index(x.type), x.cits), reverse=(True) ):
                pap.PubHtml(htmlout)
        elif (sort == 'bycits'):
            for pap in sorted(self.list, key =lambda x: (x.cits), reverse=(True) ):
                pap.PubHtml(htmlout)        
        elif (sort == 'byyear'):
            for pap in sorted(self.list, key =lambda x: (x.year), reverse=(True) ):
                pap.PubHtml(htmlout)        
        elif (sort == 'original'):
            for pap in self.list:
                pap.PubHtml(htmlout)
        elif (sort == 'reverse'):
            for pap in reversed(self.list):
                pap.PubHtml(htmlout)
        else:
            print("ERROR, not implemented")
            
    def writeCSV(self, biblist, dir, outroot):
        bibcsv =  open(dir+'/'+outroot+'bib.csv','w',encoding='ascii',errors='xmlcharrefreplace')
        print('Writing:'+dir+'/'+outroot+'bib.csv')
        for pap in self.list:
            if (pap.bibcode in biblist):
                bibcsv.write(pap.bibcode+';'+pap.authors[0]+';'+str(len(pap.authors))+
                ';'+pap.tag+';'+pap.actions[0][0]+'\n')
            


def ReadADS_Pickle(dir,file):
    papers = list(ads.SearchQuery(author="Langevelde, H.", sort="pubdate asc", rows=400))

    print('From ADS retrieved {} papers'.format(len(papers)))

    output = open(dir+'/'+file,'wb')
    pickle.dump(papers, output, pickle.HIGHEST_PROTOCOL)
    output.close()

def ReadADS4Huib():
    try:
        papers = list(ads.SearchQuery(author="van Langevelde,", sort="pubdate asc", rows=400, fl=['id', 'bibcode', 'title', 'date','citation_count', 'author', 'citation', 'pubdate', 'year', 'pub', 'volume', 'page']))
        print('From ADS retrieved {} van Langevelde papers'.format(len(papers)))        
        papers += list(ads.SearchQuery(author="Langevelde, H.", sort="pubdate asc", rows=400, fl=['id', 'bibcode', 'title', 'date','citation_count', 'author', 'citation', 'pubdate', 'year', 'pub', 'volume', 'page']))
        print('From ADS retrieved total {} papers'.format(len(papers)))
    except:
        print('No connection with ADS, no updates...')
        papers = []
    return papers

def ReadADSBib(bib):
    papers = list(ads.SearchQuery(bibcode=bib, sort="pubdate asc", rows=100, fl=['id', 'bibcode', 'title', 'date','citation_count', 'author', 'citation', 'pubdate' ]))

    return papers

def procADS(file):
    input = open(file,'rb')
    inpapers = pickle.load(input)

    print('From pickled ADS retrieved {} papers'.format(len(inpapers)))
    return inpapers
    

def CompareYearAuthorsPage( paper, ads):
    #print '>',ads.bibcode, paper.pubmag, ads.bibcode.find(paper.pubmag)
    if (ads.year == paper.year and
        #ads.bibcode.find(paper.pubmag)>0 and
        MatchPageno(paper, ads) and
        MatchMostAuthors(paper, ads) ):
            if verbose: print('Match for {}, in {} and authors: {}'.format(paper.year,paper.pubmag,paper.authors[0]))
            return True
    else:
        return False
        
def MatchPageno( paper, ads ):
    repageno = re.compile(r'\.{1,3}(\d{1,4})[A-Z]$')
    #this does not work so well, as the pageno can be subtracted
    pageno = False
    match = repageno.match(ads.bibcode)
    if (match):    
        if (paper.pubpag == match.group(1)):
            pageno = True
    return pageno

def MatchMostAuthors(paper, ads):
    reauth = [ 
        re.compile(r'^\s*((?:[\w\-]+)+)\,?\s*(\-?[A-Z]\.\s*)+\s*$'),
        re.compile(r'^\s*((?:[\w\-\']+)+)\,?\s*([A-Z][a-z\-]+\s*)+\s*$'),
        re.compile(r'^\s*((?:[\w\-\']+)+)\,?\s*([A-Z]\w+\s*(\-?[A-Z]\.\s*)*)+\s*$') ]

    authmatch = False
    #lets see if we can write a regexp that catches all authors
    if (debug):
        #This is here to test the regexp
        for adsauth in ads.author:
            tmpauth = adsauth.encode('ascii','ignore')
            match = False
            for rea in reauth:
                match =  (match or rea.match(tmpauth))
            if (not match):
                print('no match: {}'.format(adsauth.encode('ascii', 'ignore')))
        for auth in paper.authors:
            match == False
            for rea in reauth:
                match =  (match or rea.match(auth))
            if (not match):    
                print('no auth: ',auth)
    else:
        paplast = []
        adslast = []
        for auth in paper.authors:
            for rea in reauth:
                match = rea.match(auth)
                if (match): paplast.append(match.group(1))
                break
        for adsa in ads.author:
            tads = adsa.encode('ascii','ignore')
            for rea in reauth:            
                match = rea.match(tads)
                if (match): adslast.append(match.group(1))
                break
        #if (len(paplast) == 0): print 'WHAT?', paper.authors
        nsame = 0
        for papl in paplast:
            for adsl in adslast:
                if (papl == adsl): nsame+=1
        if ( len(paplast) != 0 and float(nsame)/len(paplast) > 0.74 ):
            #print 'YES',nsame,paper.tag, paper.year,paper.authors[0],' - ',ads.year,ads.bibcode,ads.author[0].encode('ascii','ignore')
            authmatch = True
    return authmatch

def CompareBibcode(adsc, papc):
   nsame = 0
   for i in range(len(adsc)):
       if (papc[i]==adsc[i]): nsame+=1
   if (nsame > 16):
      print('Same:',adsc,papc)
      return True
   else:
      return False
      
def CountByYear( ads ):
    istart = 1987
    #Huib this may need to get fixed...
    iend = 2016
    citlist = [0 for x in range(iend-istart+1)]
    years = []
    ncits = 0
    if hasattr(ads, 'citation_count'):
        ncits = ads.citation_count
    if (ncits>0):
        for code in ads.citation:
            years.append(int(code[0:4]))
        iy = 0
        year = istart
        while (year <= iend ):
            for y in years:
                if (year >= y): citlist[iy]+=1
            iy += 1
            year += 1
    #print years
    #print citlist
    return citlist

def getNonBibs(dir,file):
    nonfile = open(dir+'/'+file,'r', encoding = 'utf-8')
    nonbibs = []
    for item in nonfile:
        nonbibs.append(item.rstrip('\n'))

    return nonbibs
    
def updatePubs(adslist, mylist, nonbibs ):

    #Find whether everything on ads is in also already in our system
    nalloc = 0
    nalt = 0
    nknown = 0

    for ads in adslist:
        #loop the list on ads
        adsalloc = False
        for paper in mylist:
            #loop the local record
            if (paper.bibcode == ads.bibcode): 
                nalloc += 1
                adsalloc = True
                #if the ads is not up this fails, but 0 count returns None for 
                #ads.citation, which also can raise an exception
                try:
                    paper.cits = ads.citation_count
                    if (ads.citation_count > 0):
                        paper.citlist = ads.citation
                        #is this sorted in any way?
                        if (paper.cits != len(ads.citation)):
                            print('WARNING for', paper.bibcode,' cits:',paper.cits,' count:',len(ads.citation))
                    #print 'Check: N_cits:',paper.bibcode,paper.cits
                except:
                    print("No ADS connection, no citations")
                    paper.cits = 0
                    paper.citlist = []
            if (ads.bibcode in paper.altbibcodes ):
                nalt += 1
                adsalloc = True
        if (ads.bibcode in nonbibs):
            nknown +=1
            adsalloc = True
        if (not adsalloc):
            #print('debug',ads.bibcode, paper.altbibcodes)
            print('NEW {} :'.format(ads.bibcode ))
            newpaper = Paper()
            newpaper.fillFromAds(ads)
            mylist.append(newpaper)
    print('pub has {} papers, ads {}, matched {} primaries, {} alts and {} known non-papers'.format(len(mylist),len(adslist),nalloc,nalt,nknown))
    return mylist

def editPaperCits( paper, stats ):
    bibc = str(paper.bibcode)
    for ifield in range(len(stats['header'])):
        if (stats['header'][ifield] == 'author'):
            if (stats[bibc][ifield] != paper.authors[0].split(',')[0].encode('ascii','replace')):
                stats[bibc][ifield] = paper.authors[0].split(',')[0]
                print('updated author',stats[bibc][ifield])
        elif (stats['header'][ifield] == 'tag'):
            if (stats[bibc][ifield] != paper.tag):
                stats[bibc][ifield] = paper.tag
                print('updated tag',stats[bibc][ifield])
        elif (stats['header'][ifield] == 'type'):
            if (stats[bibc][ifield] != paper.type):
                stats[bibc][ifield] = paper.type
                print('updated type',stats[bibc][ifield])
        

def updateCits(stats, mylist, update):

    def repdifcits(paper):
        '''
        Report on the mutations in citations on paper, accumulate in ncittot, ncitsnew
        '''
    
        def repmostrecent(nnew,paper):
            '''
            Reports on the new latest papers for paper, which is an ads.entry
            '''

            def repentry(i,entry):
                if (entry['author']):
                    print('  -{:2}:   {} {} [{}], {:60}'.format(i,entry['author'], entry['bibcode'], 
                        entry['pubdate'], entry['title']))
                else:
                    print('  -{:2}:     no author {}, {:60}'.format(i, entry['bibcode'], 
                        entry['title']))
                #there could be more if the date is not unique            
                return       
        
            global Nadspol
            creps = []
            for cit in paper.citlist:
                try:
                    Nadspol += 1
                    citads = ReadADSBib(cit)
                    if debug: print(Nadspol, cit, citads[0], 'd:',citads[0].pubdate)
                    entry = { 'bibcode': cit, 'pubdate':citads[0].pubdate, 
                    'author': citads[0].author[0].split(',')[0], 
                    'title':citads[0].title[0]}
                except:
                    if debug: print(Nadspol,' failed...')
                    entry =  { 'bibcode': cit, 'pubdate': '',
                    'author': '', 
                    'title':''}
                creps.append(entry)
    
            newlist = sorted(creps, key=itemgetter('pubdate'))
            for i in range(nnew):
                repentry(i,newlist[-1-i])

            i = nnew
            nmore = 0
            while (i<(len(newlist)-1) and newlist[-1-i-1]['pubdate'] == newlist[-1-i]['pubdate']):
                nmore += 1
                repentry(i,newlist[-1-i])
                i = i+1
            if (nmore > 0): print('Included ',nmore,' entries with same pubdate.')
            return

        ncittot = 0
        ncitsnew = 0
        #print 'Consistent?',paper.cits, paper.citlist
        if (paper.cits >= 0 ):
            #this is a paper for which stats are available
            ncittot = paper.cits
            #print 'down:',ntotal, paper.cits
            if (paper.cits != paper.oldcits):
                #some citations could go from -1 to 1, with only one citation
                nnew = paper.cits - max(paper.oldcits,0)
                ncitsnew += nnew
                if (nnew < 0):
                    print('{} has citation mutations,  was {:3d}, now {:3d} (going down, likely arXiv papers resolved)'.format(paper.strSum(),paper.oldcits,paper.cits))
                else:
                    print('{} has citation mutations,  was {:3d}, now {:3d}'.format(paper.strSum(),paper.oldcits,paper.cits))
                #if you need to know, op ads for bibcode
                if (paper.cits > 0 and paper.cits < opts.maxpolads):
                    repmostrecent(nnew, paper)
                elif (paper.cits < 1):
                    print('Initialising citations...')       
                else:
                    print(paper.cits,' is more than max for polling (',opts.maxpolads,')') 
            #now update stats
            if not paper.bibcode in [pap.bib for pap in stats.papers]:
                stats.addPaper(paper.bibcode,paper.authors[0].split(',')[0],paper.tag,paper.type,paper.cits)
            else:
                if (dostatsupdate):
                    #in case tags are changed or other stuff got updated
                    editPaperCits(paper, stats)
            stats.updCits(paper.bibcode, paper.cits )
        else:
            #no stats for this paper?
            if (paper.type == 'paper'):
                print('UNABLE to update stats for ',paper.strSum())
        #if (ncitsnew>0): print 'local added',ncitsnew
        return ncittot, ncitsnew
        

    ndelta = 0 #huib, this may be the problem
    ntotal = 0
    wasdate = stats.dates[-1]
    print('Wasdate:',wasdate,' Adding:', update)
    stats.addDate(update)
    #report on any changes
    for paper in mylist:
        naddtot, ncitsadd = repdifcits(paper)
        ntotal += naddtot
        ndelta += ncitsadd
    print('Found = {} new citations for {} compared to {}'.format(ndelta,update,wasdate))
    print('Total citations: {}'.format(ntotal))
    return stats
    
def clean4Huib( adsl ):
    newads = []
    for pap in adsl:
        yeshuib = True
        for name in pap.author:
            groups = name.split(',')
            if (groups[0].find('angevel')>=0):
                if (not ((groups[1].find('H.') >= 0) or (groups[1].find('Hu')>=0))):
                    yeshuib = False
                    #print 'Not Huib:', groups[1]
        if (yeshuib): 
            newads.append(pap)
    return newads

def findLatestPub():
    repub = re.compile(r'^pub(\d{4})v3.txt$')

    latestdate = '0001'
    recentfile = ''
    foundfile = False

    matchfiles = []
    for file in os.listdir(monthdir):
        matchpub = repub.match(file)
        if matchpub:
            #filemod = time.strftime("%d%m%y", time.localtime(os.path.getmtime(file)))
            filemon = matchpub.group(1)
            matchfiles.append(file)
            if (int(filemon)>int(latestdate)):
                foundfile = True
                latestdate = filemon
                recentfile = file
    if (len(matchfiles)>0):
        #print 'found {}:'.format(matchfiles)
        #print '{} selected'.format(recentfile)
        pass
    else:
        print('No root files found')
        root = ''
    return monthdir+'/'+recentfile
    
def findLatestCSV():
    recsv = re.compile(r'^pub(\d{6}).csv$')

    latestdate = '000101'
    recentfile = ''
    foundfile = False

    matchfiles = []
    for file in os.listdir(dailydir):
        matchcsv = recsv.match(file)
        if matchcsv:
            #filemod = time.strftime("%d%m%y", time.localtime(os.path.getmtime(file)))
            filemon = matchcsv.group(1)
            matchfiles.append(file)
            if (int(filemon)>int(latestdate)):
                foundfile = True
                latestdate = filemon
                recentfile = file
    if (len(matchfiles)>0):
        #print 'CSV found {}:'.format(matchfiles)
        #print 'CSV {} selected'.format(recentfile)
        pass
    else:
        print('No root files found')
        root = ''
    return dailydir+'/'+recentfile
    
def findLatestPubRoot(dir):
    repub = re.compile(r'^pub(\d{4})v3.txt$')

    latestdate = '0001'
    recentfile = ''
    foundfile = False

    matchfiles = []
    for file in os.listdir(dir):
        matchpub = repub.match(file)
        if matchpub:
            #filemod = time.strftime("%d%m%y", time.localtime(os.path.getmtime(file)))
            filemon = matchpub.group(1)
            matchfiles.append(file)
            if (int(filemon)>int(latestdate)):
                foundfile = True
                latestdate = filemon
                recentfile = file
    if (len(matchfiles)>0):
        print('found {}:'.format(matchfiles))
        print('{} selected'.format(recentfile))
        root = 'pub'+latestdate
    else:
        print('No root files found')
        root = ''
    return root
    
def newRoot(curroot):
    def pubdate(string):
        repub = re.compile(r'^pub(\d{4})$')
        out = 0
        matchpub = repub.match(string)
        if matchpub:
            out = int(matchpub.group(1))
        return out
            
    newroot = 'pub'+dt.date.today().strftime("%y%m")
    #newroot = time.strftime("%y%m", datetime.datetime.now() )
    if (pubdate(newroot) <= pubdate(curroot)): newroot = 'pubtmp'
    print('writing to files with root: {}'.format(newroot))
    return newroot
    
def newPub(curfile):
    def pubdate(string):
        repub = re.compile(r'pub(\d{4})$')
        out = 0
        matchpub = repub.match(string)
        if matchpub:
            out = int(matchpub.group(1))
        return out
            
    newroot = monthdir+'/pub'+dt.date.today().strftime("%y%m")+version+'.txt'
    #newroot = time.strftime("%y%m", datetime.datetime.now() )
    if (pubdate(newroot) <= pubdate(curfile)): 
        newroot = dailydir+'/pubtmp'+version+'.txt'
    #print 'writing to files with root: {}'.format(newroot)
    return newroot
    
def newCSV(curcsv):
    #in the same month, write a daily csv, new month, write a 4 string
    def pubdatemon(string):
        repub = re.compile(r'pub(\d{4})')
        out = 0
        matchpub = repub.match(string)
        if matchpub:
            out = int(matchpub.group(1))
        return out
            
    newroot = monthdir+'/pub'+dt.date.today().strftime("%y%m")+'.csv'
    #newroot = time.strftime("%y%m", datetime.datetime.now() )
    if (pubdatemon(newroot) <= pubdatemon(curcsv)): 
        newroot = dailydir+'/pub'+dt.date.today().strftime("%y%m%d")+'.csv'
    #print 'writing to files with root: {}'.format(newroot)
    return newroot
    
def pubRoot(filename):
    reroot = re.compile(r'(pub(?:tmp|\d{4,6}))')
    matchroot = reroot.search(filename)
    out = ''
    if matchroot:
        out = matchroot.group(1)
    else:
        print('This is not possible: no pub in string',filename)
    return out
    
def compfile(filename):
    '''returns a compact name for our files'''
    home = rootdir
    replhome = '~'
    return filename.replace(home, replhome)
    
def readBibCSV(infile):
    inf = open(infile,'r',encoding='ascii')
    print('Reading biblist from',infile)
    biblist=[]
    pltaglist=[]
    for line in inf:
        fields = line.rstrip('\n').split(';')
        if debug: print('Bib fields:',fields)
        biblist.append(fields[0])
        pltaglist.append(fields[3])
    return biblist,pltaglist

#-----------------------------------------------------------------------------------------
# Main starts


#find the most recent file
#define output root
opts = GetArgs()
#print opts.plot, opts.noupdate
dodir = '.'

mylist = ListPapers()

inpubfile = findLatestPub()
outpubfile = newPub(inpubfile)
print('Pub Files, in:',compfile(inpubfile),' out:',compfile(outpubfile))

incsvfile = findLatestCSV()
outcsvfile = newCSV(incsvfile)
print('CSV Files, in:',compfile(incsvfile),' out:',compfile(outcsvfile))

if debug: print("...Reading in data")
mylist.ReadPubV3(inpubfile, pubencoding)
if debug: print("...Reading in stats")
curstats = CitStats()
curstats.readStats(incsvfile)

#now = datetime.datetime.now()
nows = str(dt.datetime.now().date())
update=nows[8:10]+'/'+nows[5:7]+'/'+nows[2:4]

recdate=curstats.mostRecent()
print('Today:',update, ' compare to:', recdate)

mylist.addStats(curstats)
outroot = pubRoot(outpubfile)

theBibs = []; pltTags = []
if (opts.coauth != ''):
    print('NEW:',opts.coauth)
    theBibs = mylist.SelCoAuth(opts.coauth)
    print('Finding these:',theBibs)
elif (opts.bibfile != ''):
    theBibs,pltTags = readBibCSV(opts.bibfile)
    print('Using these bibs:',theBibs)

if debug: print("...Start update")

if (not opts.noupdate):
    print("Do update:")
    fadslist = ReadADS4Huib()
    adslist = clean4Huib(fadslist)
    fileroot = pubRoot(inpubfile)
    nonbibs = getNonBibs(monthdir,fileroot+'_nopaper.txt')
    newlist = ListPapers()
    newlist.list = updatePubs(adslist, mylist.list, nonbibs )
    updateCits(curstats, newlist.list, update)
    newlist.FullList(outpubfile,pubencoding)    
    curstats.writeStats(outcsvfile)
    #newlist.checkFiles()
    copyfile(monthdir+'/'+fileroot+'_nopaper.txt', monthdir+'/'+outroot+'_nopaper.txt')


curstats.reportCits( opts.plot, opts.window, opts.yscale, theBibs, pltTags )
mylist.writeHtml(opts.sort, dailydir, outroot)
    #mylist.checkFiles()
    
if (len(theBibs) != 0):
    mylist.writeCSV(theBibs,dailydir,outroot)

