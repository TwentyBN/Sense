#!/usr/bin/env python
"""
Real time detection of 30 hand gestures.

Usage:
  gesture_recognition.py [--camera_id=CAMERA_ID]
                         [--path_in=FILENAME]
                         [--path_out=FILENAME]
                         [--custom_classifier=PATH]
                         [--title=TITLE]
                         [--use_gpu]
  gesture_recognition.py (-h | --help)

Options:
  --path_in=FILENAME              Video file to stream from
  --path_out=FILENAME             Video file to stream to
  --custom_classifier=PATH        Path to the custom classifier to use
  --title=TITLE                   This adds a title to the window display
"""
import torch
import os
import json
from docopt import docopt

import realtimenet.display
from realtimenet import camera
from realtimenet import engine
from realtimenet import feature_extractors
from realtimenet.downstream_tasks.gesture_recognition import INT2LAB
from realtimenet.downstream_tasks.nn_utils import Pipe, LogisticRegression
from realtimenet.downstream_tasks.postprocess import PostprocessClassificationOutput


if __name__ == "__main__":
    # Parse arguments
    args = docopt(__doc__)
    camera_id = args['--camera_id'] or 0
    path_in = args['--path_in'] or None
    path_out = args['--path_out'] or None
    custom_classifier = args['--custom_classifier'] or None
    title = args['--title'] or None
    use_gpu = args['--use_gpu']

    # Load feature extractor
    feature_extractor = feature_extractors.StridedInflatedEfficientNet()
    checkpoint = torch.load('resources/strided_inflated_efficientnet.ckpt')
    feature_extractor.load_state_dict(checkpoint)
    feature_extractor.eval()

    # Load a logistic regression classifier
    if custom_classifier is not None:
        with open(os.path.join(custom_classifier, 'class2int.json')) as file:
            class2int = json.load(file)
            INT2LAB = {value: key for key, value in class2int.items()}
            num_out = len(INT2LAB)
    else:
        num_out = 30
    gesture_classifier = LogisticRegression(num_in=feature_extractor.feature_dim,
                                            num_out=num_out)
    checkpoint = torch.load(os.path.join(custom_classifier, 'classifier.checkpoint'))
    gesture_classifier.load_state_dict(checkpoint)
    gesture_classifier.eval()

    # Concatenate feature extractor and met converter
    net = Pipe(feature_extractor, gesture_classifier)

    # Create inference engine, video streaming and display instances
    inference_engine = engine.InferenceEngine(net, use_gpu=use_gpu)

    video_source = camera.VideoSource(camera_id=camera_id,
                                      size=inference_engine.expected_frame_size,
                                      filename=path_in)

    framegrabber = camera.VideoStream(video_source,
                                      inference_engine.fps)

    postprocessor = [
        PostprocessClassificationOutput(INT2LAB, smoothing=4)
    ]

    display_ops = [
        realtimenet.display.DisplayTopKClassificationOutputs(top_k=1, threshold=0.5),
    ]
    display_results = realtimenet.display.DisplayResults(title=title, display_ops=display_ops)

    engine.run_inference_engine(inference_engine,
                                framegrabber,
                                postprocessor,
                                display_results,
                                path_out)
