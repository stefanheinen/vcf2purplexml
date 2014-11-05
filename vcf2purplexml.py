#!/usr/bin/env python
"""Converts a vcard or csv file to a libpurple buddylist xml file for use with whatsapp-purple"""

import sys
import os.path
import csv
import collections
import codecs
import argparse

import phonenumbers
import pystache
import vobject


# command line argument magic
parser = argparse.ArgumentParser(description="Reads a csv-file with contacts and converts it into an xml-file for pidgin")
parser.add_argument('-o', '--ownNumber', help='your own cellphone number (whatsapp username) in international format without leading zero, e.g. 43123456789', default='0')
parser.add_argument('-x', '--excludeCategories', nargs='+', help='contacts which have one of this categories set will be ignored', default=['Archiv'])
parser.add_argument('-n', '--noCategory', help='', default='others')
parser.add_argument('-e', '--escapeChar', help='escape character used in the input csv-file', default='\\')
parser.add_argument('-c', '--countryCode', help='2-letter country code from which to interpret phone numbers', default='DE')
parser.add_argument('-f', '--fileType', help='set the filetype of the inputFile', choices=['vcf', 'csv'])
parser.add_argument('-t', '--templateFile', help='set the template file', default='blist.xml.template')
parser.add_argument('inputFile', nargs='?')
parser.add_argument('outputFile', nargs='?')
parser.add_argument('templateFile', nargs='?', default='blist.xml.template')
args = parser.parse_args()


def get_index(seq, attr, value):
    """returns the index of an element with a certain key and value"""
    return next((index for (index, d) in enumerate(seq) if d[attr] == value), -1)

def readCsv(csvFile):
    """Reads a csv-file and returns a list of tuples of (FN, categories_list, telephonenumber_list)"""
    contacts = []
    for row in csv.DictReader(csvFile, escapechar=args.escapeChar):
        if None in row: del row[None]
        
        fn = ''
        try:
            fn = row.get("FN")
        except:
            continue
            
        categories = []
        try:
            categories = row.get("CATEGORIES").split(",")
        except:
            pass    
            
        # get the cellphone numbers
        telCells = {k:v for k,v in row.iteritems() if k.find("TEL") != -1}

        tel_list = []
        for k,v in telCells.iteritems():
            if v == '':
                continue
            params = k.split(";")
            params.pop(0)
            paramsDict = collections.defaultdict(list)
            for param in params:
                paramName,paramValue = param.split("=")
                paramsDict[paramName.upper()].append(paramValue)
            
            tel_list.append( (v, paramsDict) )

        contacts.append( (fn, categories, tel_list) )
    return contacts

def readVcf(vcfFile):
    """Reads a vcf-file and returns a list of tuples of (FN, categories_list, telephonenumber_list)"""
    vobjs = vobject.readComponents(vcfFile)
    contacts = []
    for v in vobjs:
        fn = ''
        try:
            fn = v.fn.value
        except:
            continue

        categories = []
        try:
            categories = v.categories.value
        except:
            pass
        
        tel_list = []
        try:
            for t in v.tel_list:
                tel_list.append( (t.value, t.params) )
        except:
            continue

        contacts.append( (fn, categories, tel_list) )

    return contacts


# open in/outFiles (or stdin/stdout if not specified) 
if args.inputFile:
    try:
        inFile = open(args.inputFile)
    except IOError as e:
        print "Error opening input file: " + args.inputFile
        print "I/O error({0}): {1}".format(e.errno, e.strerror)
        sys.exit();
else:
    inFile = sys.stdin

if args.outputFile:
    try:
        outFile = codecs.open(args.outputFile, 'w', 'utf-8')
    except IOError as e:
        print "Error opening output file: " + args.outputFile
        print "I/O error({0}): {1}".format(e.errno, e.strerror)
        sys.exit();
else:
    outFile = codecs.getwriter('utf-8')(sys.stdout)

# determine filetype
fileType = ''
if args.fileType:
    fileType = args.fileType
else:
    if args.inputFile:
        extension = os.path.splitext(args.inputFile)[1]
        if extension == '.csv':
            fileType = 'csv'
        elif extension == '.vcf':
            fileType = 'vcf'

# if filetype couldn't be determined by argument or extension default to vcf
# then read the file
if fileType == 'csv':
    contacts = readCsv(inFile)
else:
    contacts = readVcf(inFile)

inFile.close()

#prepare output templateValues
templateValues = {"ownNumber": args.ownNumber,
                  "groups": []}
grouplist = templateValues["groups"]

# go through contacts and put valid ones into the correct categories in templateValues
# valid meaning the name is not empty and has at least one valid telephonenumber which is not a landline
for name,categories,telnumbers in contacts:
    if name == "":
        continue
    if [i for i in categories if i in args.excludeCategories]:
        continue
    
    # get the cellphone numbers
    prefCellNumbers = []
    cellNumbers = []
    for number,params in telnumbers:
        # skip if number is not a valid phone number
        try:
            pn = phonenumbers.parse(number, args.countryCode)
        except:
            continue
        if not phonenumbers.is_valid_number(pn):
            continue

        # skip if number is a fixed line
        if phonenumbers.phonenumberutil.number_type(pn) == phonenumbers.phonenumberutil.PhoneNumberType.FIXED_LINE:
            continue
 
        # reformat number to "491234567890" format
        cellNumber = str(pn.country_code) + str(pn.national_number)

        # avoid duplicates
        if number in prefCellNumbers + cellNumbers:
            continue

        if 'TYPE' in params and 'pref' in params['TYPE']:
            prefCellNumbers.append(cellNumber)
        else:
            cellNumbers.append(cellNumber)
    cellNumbers = prefCellNumbers + cellNumbers

    if len(cellNumbers) == 0:
        continue

    buddies = list()
    for cellNumber in cellNumbers:
        buddies.append({"number": cellNumber, "alias": name})

    if len(categories) == 0:
        categories.append('')

    for category in categories:
        if category == '':
            category = args.noCategory
            
        i = get_index(grouplist, "groupname", category)
        if i == -1:
            grouplist.append({"groupname": category, "contacts": []})
            i = get_index(grouplist, "groupname", category)

        grouplist[i]["contacts"].append({"buddies": buddies[:]})

# initialize a pystache renderer and fill the template file with the templateValues
# and then write the file to outFile
rend = pystache.Renderer(file_encoding="utf-8", string_encoding="utf-8", file_extension=False)
temp = rend.load_template(args.templateFile)
outFile.write(rend.render(temp, templateValues))

outFile.close()
