import glob
from lxml import etree
from bs4 import BeautifulSoup
import csv
import os.path
import json

# presumes holdings pages have been downloaded locally

holdings = glob.glob('holdings/*.html')

# example page: https://chroniclingamerica.loc.gov/lccn/sn85042399/holdings/

allrows  = [] # to receive rows of data for writing out

for page in holdings:
	# extract entity id value, the sn value from the file name
    sn = page.replace('holdings/', '').replace('.html', '')

    # open the file, parse via BS to clean, then punt to lxml to parse
    with open(page, 'r') as fin:
        soup = BeautifulSoup(fin.read(), 'lxml')
        tree = etree.fromstring(soup.prettify())

    # apply xpath to dig into the div with the holdings info, selecting that node.
    # stringify it to get the raw html out of it, which sanitizes the newlines
    # so we have to desanitize them.
    divstr = str(etree.tostring(tree.xpath('//div[@id = "std_box"]')[0])).replace('\\n', '\n')

    # these values are highly variable, with the only delimiter being the word HOLDING.
    splits = divstr.split(str('HOLDING'))

    # when you split like this there's always some bit of garbage at the beginning
    splits.pop(0)

    # now we're left with some independent chunks of html, each theoretically a 
    # holdings record
    for record in splits:

    	# get rid of all that extra white space from the xml formatting.
        s = [l.strip() for l in record.split('\n')]

        # the location is always the first string to pop up, also cleaning out whitespace
        location = s[0].replace(':','').strip()

        # find the location of the h4, as it marks the availability type
        h4loc = s.index('<h4 class="holding">')

        # sometimes there are multiple, so repeating the splitting and garbage cleaning process
        holdingschunks = "\n".join(s[h4loc:]).split('Available')
        holdingschunks.pop(0)

        # looping through the available formats for that holding record
        for line in holdingschunks:
            datechunks = line.split('\n')
            # not all dates have <ul>, so brute force it is
            # the following is used to determine the range of lines where these dates are reported
            fmt = datechunks[0].replace("as:", '').strip()
            if 'Dates' in line:
                for i, l in enumerate(datechunks):
                    if "Dates:" in l:
                        start = i
            else:
                start = 0
            for i, l in enumerate(datechunks):
                if "Last updated:" in l:
                    stop = i
            # slice out the dates, cancat the lines together
            # then plunk them in a root element (f for FML at this point) to be valid XML
            # then extract the text out and be done with it.
            # the pure text chunk was needed here, thankfully.
            datetext = BeautifulSoup("<f>" + "".join(datechunks[start + 1:stop]) + "</f>", 'lxml').get_text()
            
            # this date chunk is the most granualr row of information
            # so add it to the empty list, which becomes the core stub value
            # for out csv.
            allrows.append([sn, location, fmt, datetext])

# now that we have that mess sorted, let's turn eyes toward the easy ones.

# go through the previously harvested marc and json records for this newspaper
# they have the remaining values we want.
# why some of this info exists in the json api value and not in the marc xml is beyond me

morerows = []


# read open the previously collected rows of data and extract the info
# this will read and parse the same file multiple times, but this scale isn't
# such that it matters.  This lends for cleaner code.
for row in allrows:
    sn, location, fmt, datetext = row
    # determine marc xml file name, open, and parse
    marc = 'marc/' + sn + '.xml'
    with open(marc, 'r') as fin:
        tree = etree.fromstring(fin.read())

    # extract desired values
    oclc = tree.xpath('//controlfield[@tag = "001"]/text()')[0]
    title = tree.xpath('//datafield[@tag = "245"]/subfield[@code = "a"]/text()')[0]
    # frequency have many values over time, smashing together per spec
    freq = " ".join(tree.xpath('//datafield[@tag = "310"]//text()'))

    # generate json file name, open, and parse
    jsonname = 'jsons/' + sn + '.json'
    with open(jsonname, 'r') as fin:
        data = json.loads(fin.read())
    startyear = data['start_year']
    endyear = data['end_year']

    # now we have all the info we want, we can write out our final row of data for the csv
    newrow = [sn, title, location, fmt, oclc, startyear, endyear, freq, datetext]
    morerows.append(newrow)


# now write out the rows to a csv

with open('holdings.csv', 'w') as fout:
    csvout = csv.writer(fout)
    csvout.writerow(['sn', 'title', 'location', 'format', 'oclc', 'startyear', 'endyear', 'freq', 'material_dates'])
    csvout.writerows(morerows)