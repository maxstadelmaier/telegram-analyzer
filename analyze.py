# Copyright (C) 2022  Alexander Kraus <nr4@z10.info>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from os import listdir
from os.path import isfile, join
from html.parser import HTMLParser
from operator import itemgetter
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import argparse
import functools
from scipy.signal import correlate
import numpy

class Message:
    def __init__(self, author, message, date):
        self.author = author
        self.message = message
        self.date = date

    def toString(self):
        return self.author + "(" + self.date + "): " + self.message

    def dateTime(self):
        try:
            return datetime.strptime(self.date, '%d.%m.%Y %H:%M:%S')
        except:
            self.date = self.date.split(' UTC')[0]
            return datetime.strptime(self.date, '%d.%m.%Y %H:%M:%S')

class ChatParser(HTMLParser):
    def __init__(self):
        super().__init__()
        
        self.messageAuthor = None
        self.messageText = None
        self.messageDate = None
        self.makeNextDataName = False
        self.makeNextDataText = False
        self.messages = []

    def handle_starttag(self, tag, attributes):
        makeNextAttributeDate = False

        for (attributeName, attributeValue) in attributes:
            if makeNextAttributeDate:
                if attributeName == "title":
                    self.messageDate = attributeValue.strip()
                    makeNextAttributeDate = False

            if attributeName == "class":
                classList = attributeValue.split(' ')

                if "message" in classList:
                    if self.messageDate != None and self.messageAuthor != None and self.messageText != None:
                        self.messages += [Message(self.messageAuthor, self.messageText, self.messageDate)]
                        self.messageAuthor = None
                        self.messageText = None
                        self.messageDate = None
                elif "date" in classList:
                    makeNextAttributeDate = True
                elif "from_name" in classList:
                    self.makeNextDataName = True
                elif "text" in classList:
                    self.makeNextDataText = True

    def handle_data(self, data):
        if self.makeNextDataName:
            self.messageAuthor = data.replace(" via @gif", "").strip()
            self.makeNextDataName = False

        if self.makeNextDataText:
            self.messageText = data.strip()
            self.makeNextDataText = False

    def contributingNames(self):
        return list(set(map(
            lambda message: message.author,
            self.messages,
        )))

    def contributorMessages(self, name):
        return list(map(
            lambda message: message.message,
            filter(
                lambda message: message.author == name,
                self.messages,
            ),
        ))

    def contributorNumberOfChars(self, name):
        return functools.reduce(
            lambda accumulator, addition: accumulator + addition,
            map(
                lambda message: len(message),
                self.contributorMessages(name),
            ),
        )
    
    def contributorNumberOfWords(self, name):
        return functools.reduce(
            lambda accumulator, addition: accumulator + addition,
            map(
                lambda message: len(message.split(' ')),
                self.contributorMessages(name),
            ),
        )

    def contributorNumberOfMessages(self, name):
        return len(self.contributorMessages(name))

    def contributorTimeline(self, name):
        messagesPerDate = dict()

        for message in self.messages:
            if message.author == name:
                dateTimeOfMessage = message.dateTime()
                if dateTimeOfMessage.date() in messagesPerDate:
                    messagesPerDate[dateTimeOfMessage.date()] += 1
                else:
                    messagesPerDate[dateTimeOfMessage.date()] = 1

        if not datetime.now().date() in messagesPerDate:
            messagesPerDate[datetime.now().date()] = 0

        sortedMessagesPerDate = sorted(messagesPerDate)

        totalMessages = 0
        timeline = dict()
        for date in sortedMessagesPerDate:
            totalMessages += messagesPerDate[date]
            timeline[date] = totalMessages

        return timeline
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser('KBK chat analysis tool')
    parser.add_argument('-d', dest='directory')
    parser.add_argument('-o', dest='output')
    parser.add_argument('-c', dest='correlation', action='store_true')
    parser.add_argument('-t', dest='timeline', action='store_true')
    args = parser.parse_args()

    chatProtocolFiles = [filename for filename in listdir(args.directory) if isfile(join(args.directory, filename))]

    chatParser = ChatParser()

    for chatProtocolFile in chatProtocolFiles:
        completeFilePathName = join(args.directory, chatProtocolFile)

        print("Parsing file:", completeFilePathName)

        chatParser.feed(open(completeFilePathName, "r", encoding='utf8', errors='ignore').read())

    contributorData = list(map(
        lambda contributor: [
            contributor,
            chatParser.contributorNumberOfMessages(contributor),
            chatParser.contributorNumberOfWords(contributor),
            chatParser.contributorTimeline(contributor),
            chatParser.contributorMessages(contributor),
        ],
        chatParser.contributingNames(),
    ))
    
    contributorDataSortedByNMessages = list(reversed(sorted(contributorData, key=itemgetter(1))))

    # Contribution timeline
    if args.timeline:
        figure = plt.figure()

        for contributorData in contributorDataSortedByNMessages[:20]:
            contributor = contributorData[0]
            nMessages = contributorData[1]
            nWords = contributorData[2]
            timeline = contributorData[3]

            print("Contributor", contributor, "has contributed", nMessages, "messages with", nWords, "words.")

            plt.plot_date(timeline.keys(), timeline.values(), '', label=contributor)

        plt.legend()
        plt.grid()
        plt.xlabel("Verstrichene Lebenszeit")
        plt.ylabel("Anzahl von Nachrichten")
        plt.title("Spammer-Highscore @KBK (c) KBK {}".format(
            datetime.now().year,
        ))

        figure.set_size_inches([16,9])
        figure.savefig(args.output, dpi=180)

    # Cross correlation matrix.
    if args.correlation:
        figure = plt.figure()

        correlationMatrix = numpy.zeros((len(contributorDataSortedByNMessages), len(contributorDataSortedByNMessages)))

        indices = range(len(contributorDataSortedByNMessages))

        for i in indices:
            firstContributorData = contributorDataSortedByNMessages[i]
            for j in indices:
                secondContributorData = contributorDataSortedByNMessages[j]
                firstTimeline = firstContributorData[3]
                secondTimeline = secondContributorData[3]

                # For cross corellation we need the same timestamps present in both signals.
                # 1.) Determine common time interval.
                # 2.) Fill timeline keys per day in this interval.
                # 3.) Cross-correlate.
                sortedFirst = sorted(firstTimeline.keys())
                sortedSecond = sorted(secondTimeline.keys())

                firstCommonDate = max(sortedFirst[0], sortedSecond[0])
                lastCommonDate = min(sortedFirst[-1], sortedSecond[-1])

                if firstCommonDate not in firstTimeline or firstCommonDate not in secondTimeline or \
                    lastCommonDate not in firstTimeline or lastCommonDate not in secondTimeline:
                    print("Problem with cross corelation of {} and {} - not enough common data.".format(
                        firstContributorData[0],
                        secondContributorData[0],
                    ))
                    continue

                lastFirstDate = firstCommonDate
                lastSecondDate = firstCommonDate
                date = firstCommonDate
                commonFirstTimeline = {}
                commonSecondTimeline = {}
                while date != lastCommonDate:
                    lastFirstDate = date if date in sortedFirst else lastFirstDate
                    lastSecondDate = date if date in sortedSecond else lastSecondDate
                    date += timedelta(days=1)
                    commonFirstTimeline[date] = firstTimeline[date if date in firstTimeline else lastFirstDate]
                    commonSecondTimeline[date] = secondTimeline[date if date in secondTimeline else lastSecondDate]

                crossCorrelation = correlate(list(map(float, commonFirstTimeline.values())), list(map(float, commonSecondTimeline.values())))

                sumOfCrossCorrelation = functools.reduce(
                    lambda accumulator, addition: accumulator + addition,
                    crossCorrelation,
                )

                correlationMatrix[i,j] = numpy.log10(1.+sumOfCrossCorrelation/len(commonFirstTimeline.values())/len(commonSecondTimeline.values())/len(crossCorrelation))

        (contributorNames,) = list(map(
            lambda _contributorData: _contributorData[0][:11] + "..." if len(_contributorData[0]) > 14 else _contributorData[0],
            contributorDataSortedByNMessages,
        )),
        print(contributorNames)

        plt.subplots_adjust(bottom=0.15, left=0.15)

        plt.xticks(indices, contributorNames, rotation=90)
        plt.yticks(indices, contributorNames)

        plt.title("Trigger-Cross-Correlation (log10-scale) @KBK (c) KBK {}".format(
            datetime.now().year,
        ))

        colorPlot = plt.pcolor(indices, indices, correlationMatrix, cmap="RdBu_r", edgecolor='k')
        axes = plt.gca()

        axes.tick_params(axis='both', which='major', pad=3)
        figure.colorbar(colorPlot, ax=axes, extend='max')


        figure.set_size_inches([10.5,9])
        figure.savefig(args.output, dpi=180)
