import requests
import os
import numpy as np
import sys
from bs4 import BeautifulSoup
import re
from wordcloud import WordCloud, STOPWORDS
from PIL import Image, UnidentifiedImageError
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import argparse
from tqdm import tqdm
from math import ceil
import warnings

def main():
    api_url, accountname, accessToken, mask, cloud, stopwords_file, \
      contour_color, contour_width = wc_args()
    accountID, status_count = get_accountID(api_url, accountname, accessToken)
    word_dict = get_word_frequencies(api_url, accountID, accessToken,
                                     status_count)
    remove_stopwords(word_dict, stopwords_file)
    create_wordcloud(word_dict, mask, cloud, contour_color,
                     contour_width)

def wc_args():
    parser = argparse.ArgumentParser(description="Create a wordcloud from "
                                                 "Mastodon")
    parser.add_argument("server_url", help="The server's URL i.e. "
                                            "https://fosstodon.org")
    parser.add_argument("account_name", help="The account name: i.e. bigeatie")
    parser.add_argument("access_token", help="The access token. Get this from "
                                             "your home instance")
    parser.add_argument("--stopwords", help="File containing one stopword per "
                                             "line", default="stopwords.txt")
    parser.add_argument("--mask_img", help="Masking image for word cloud. "
                                           "Defines the shape of the wordcloud",
                        default="pngwing.com.png")
    parser.add_argument("--output", help="Filename of the generated wordcloud",
                        default="wc.png")
    parser.add_argument("--contour_color", help="Color of the masking image "
                                                "contour. Must be a matplotlib "
                                                "color name or hex value i.e. "
                                                "#rrggbb",
                        default="gold")
    parser.add_argument("--contour_width", help="Width of the contour of the "
                                                "masking image",
                        default=2, type=int)
#    parser.add_argument("--config", help="File you can save above parameters "
#                                         "to, with one parameter per line in "
#                                         "the format "
#                                         "parameter_name=parameter_value. "
#                                         "Values passed at the command line "
#                                         "overwrite anything in this file.")
    args = parser.parse_args()

    if args.stopwords:
        if not os.path.isfile(args.stopwords):
            print(f"The stopwords file {args.stopwords} could not be found")
            sys.exit(1)

    try:
        Image.open(args.mask_img)
    except FileNotFoundError:
        print(f"No file found at {mask_file}.")
        sys.exit(1)
    except UnidentifiedImageError:
        print(f"{mask_file} not identified as an image.")
        sys.exit(1)

    if not (re.search("#[0-9A-Fa-f]{6}", args.contour_color) or
            args.contour_color in mcolors.cnames):
        print(f"The contour_color must either be a color identifiable by "
              f"matplotlib or an rgb value of the format #rrggbb. If the "
              f"latter doesn't work, try quoting it.")
        sys.exit(1)

    return (args.server_url, args.account_name, args.access_token,
            args.mask_img, args.output, args.stopwords, args.contour_color,
            args.contour_width)

def get_accountID(api_url, accountname, accessToken):
    print("Finding the account's ID...")
    response = requests.get(api_url+'api/v2/search?q='+accountname +
                              '&resolve=true&limit=1',
                            headers={'Authorization': 'Bearer '
                                     +accessToken})
    accountID =  response.json()["accounts"][0]["id"]
    status_count = response.json()["accounts"][0]["statuses_count"]
    return accountID, status_count

def get_word_frequencies(api_url, accountID, accessToken, status_count):
    print("Calculating word frequencies...")
    word_dict = {}
    payload = {"max_id": None}
    iteration = 1
    pbar = tqdm(total=ceil(status_count/20))
    while True:
        response = requests.get(api_url+'api/v1/accounts/'+accountID+'/statuses',
                                headers={'Authorization': 'Bearer '+accessToken},
                                params=payload)
        for status in response.json():
            if status["content"] is not None:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    soup = BeautifulSoup(status["content"])
                message = ""
                for d in soup:
                    message = message + " " + d.get_text(separator = " ")
                words = message.lower().split()
                i = 0
                while i < len(words):
                    if words[i] == "@":
                        i = i+2
                        continue
                    elif words[i] == "#" \
                    or words[i].startswith("http") \
                    or words[i].startswith("@") \
                    or ".com" in words[i]:
                        i = i+1
                        continue
                    else:
                        if re.search(r"[A-Za-z-]+", words[i]):
                            word = re.findall(r"[A-Za-z'-]+", words[i])[0]
                        else:
                            i = i + 1
                            continue
                        if not word in word_dict:
                            word_dict[word] = 1
                        else:
                            word_dict[word] = word_dict[word] + 1
                        i = i+1
        if len(response.json()) == 0:
            break
        payload["max_id"] = int(response.json()[-1]["id"])-1
        iteration = iteration + 1
        pbar.update(1)
    pbar.close()
    return word_dict

def remove_stopwords(word_dict, stopwords_file):
    print("Removing stopwords...")
    stopwords = set(STOPWORDS)
    with open(stopwords_file) as f:
        for line in f:
            stopwords.add(line.rstrip())
    for key in word_dict.copy().keys():
        if key in stopwords:
            word_dict.pop(key, None)

def create_wordcloud(word_dict, mask_file, output_file, contour_color,
                     contour_width):
    print("Creating wordcloud...")
    mask = np.array(Image.open(mask_file))
    wc = WordCloud(margin=5,
                contour_width=2,
                contour_color=contour_color,
                mask=mask,
                max_words=100,
                normalize_plurals=True).generate_from_frequencies(word_dict)
    wc.to_file(output_file)

if __name__ == "__main__":
    main()
