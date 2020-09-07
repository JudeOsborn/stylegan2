import numpy as np
from PIL import Image
import dnnlib

from flask import Flask, request, send_file
from flask_cors import cross_origin
from os import environ, makedirs
from subprocess import run
from glob import glob
from math import sqrt
from shutil import rmtree

import run_generator

app = Flask(__name__)

network = environ.get('NETWORK', None)
if network == None:
    print("Set env var NETWORK to stylegan pkl")
    exit()


@app.route("/stylegan/morph", methods=["POST"])
@cross_origin()
def morph():
    image_1 = request.json['image1']
    image_2 = request.json['image2']
    fc = request.json['frame_count']
    if fc is None:
        fc = 9
    # floor the resolution
    frames = int(sqrt(fc)) ** 2


    # ensure that our morphs are always alphabetically sorted
    image_1, image_2 = sorted([image_1, image_2])

    try:
        projection_patt = 'w_latents/{}*.npy'
        npy_1 = glob(projection_patt.format(image_1))[0]
        npy_2 = glob(projection_patt.format(image_2))[0]
    except IndexError:
        return "projection for one or both images not found", 400


    ws_1 = run_generator._parse_npy_files(npy_1)
    ws_2 = run_generator._parse_npy_files(npy_2)

    kwargs = {
        'network_pkl': network,
        'truncation_psi': 1.0,
        'walk_type': 'line-w',
        'frames': frames,
        'npys': [ws_1, ws_2],
        'npys_type': 'w',
        'result_dir': 'server_walk_results',
        'seeds': [],
        'save_vector': False
    }

    sc = dnnlib.SubmitConfig()
    sc.num_gpus = 1
    sc.submit_target = dnnlib.SubmitTarget.LOCAL
    sc.local.do_not_copy_source_files = True
    sc.run_dir_root = kwargs.pop('result_dir')
    sc.run_desc = "serve-latent-walk"
    result_path, _ = dnnlib.submit_run(
        sc, 'run_generator.generate_latent_walk', **kwargs)
    morph_pattern = "{}/*.png".format(result_path)
    sheet = make_spritesheet(morph_pattern, image_1+image_2)
    # delete result_path since we have our sheet
    # rmtree(result_path)
    # TODO: upload to bucket instead of storing locally
    # return the file
    return send_file(sheet)

def make_spritesheet(pattern, output_name):
    # make sure output dir exists
    makedirs("spritesheets", exist_ok=True)
    # count images
    result_imgs = glob(pattern)
    edge_count = sqrt(len(result_imgs))
    assert(edge_count % 1 == 0) # ensure we have a square number
    # run image magick
    output_path = "spritesheets/{}.png".format(output_name)
    # montage *.png -geometry 512x512 -colors 32 spritesheets/example.png
    run([
        "montage", pattern, "-geometry 512x512", "-colors 32", output_path
    ])
    return output_path


