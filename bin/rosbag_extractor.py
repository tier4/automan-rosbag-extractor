#!/usr/bin/env python
import argparse
import json
import cv2
from cv_bridge import CvBridge
import numpy as np
import os
from rosbag.bag import Bag
import sys
from pypcd import PointCloud
sys.path.append(os.path.join(os.path.dirname(__file__), '../libs'))
from core.storage_client_factory import StorageClientFactory
from core.automan_client import AutomanClient

import rosbag
import rospy
import termcolor
import tf
import tf2_py


class UnknownCalibrationFormatError(Exception):
    pass


class RosbagExtractor(object):

    @classmethod
    def extract(cls, automan_info, file_path, topics, output_dir, raw_data_info, calibfile=None):
        extrinsics_mat, camera_mat, dist_coeff = None, None, None
        if calibfile:
            try:
                calib_path = calibfile
                extrinsics_mat, camera_mat, dist_coeff = cls.__parse_calib(calib_path)
            except Exception:
                raise UnknownCalibrationFormatError
        candidates, topics = cls.__get_candidates(
            automan_info, int(raw_data_info['project_id']), int(raw_data_info['original_id']), raw_data_info['records'])
        topic_msgs = {}
        for topic in topics:
            topic_msgs[topic] = ""

        try:
            frame_time = []
            count = 0
            transforms = []
            with Bag(file_path) as bag:
                tf_buffer = tf2_py.BufferCore(rospy.Duration(3600))
                for topic, msg, t in bag.read_messages(topics=['/tf']):
                    for msg_tf in msg.transforms:
                        tf_buffer.set_transform(msg_tf, "default_authority")

                for topic, msg, t in bag.read_messages():
                    if topic in topics:
                        topic_msgs[topic] = msg
                    if all(msg != '' for msg in topic_msgs.values()):
                        count += 1
                        for c in candidates:
                            save_msg = topic_msgs[c['topic_name']]
                            output_path = output_dir + str(c['candidate_id']) \
                                + '_' + str(count).zfill(6)
                            if(c['msg_type'] == 'sensor_msgs/PointCloud2'):
                                cls.__process_pcd(save_msg, output_path)
                            else:
                                cls.__process_image(
                                    save_msg, c['msg_type'], output_path, camera_mat, dist_coeff)
                        frame_time.append({
                            'frame_number': count,
                            'secs': t.secs,
                            'nsecs': t.nsecs,
                        })
                        for topic in topics:
                            topic_msgs[topic] = ''

                transforms = [None for i in range(count)]
                for topic, msg, t in bag.read_messages(topics=['/concatenated/pointcloud_raw']):
                    try:
                        map_to_base_link = tf_buffer.lookup_transform_core("map", msg.header.frame_id, msg.header.stamp)
                        if map_to_base_link.transform.translation.x == 0.0 and map_to_base_link.transform.translation.y == 0.0 and map_to_base_link.transform.translation.z == 0.0:
                            map_to_base_link = None
                    except (tf2_py.LookupException, tf2_py.ConnectivityException, tf2_py.ExtrapolationException):
                        map_to_base_link = None
                    if map_to_base_link is not None:
                        seq_num = msg.header.seq
                        transforms[seq_num] = cls.__transform_to_dict(seq_num, map_to_base_link.transform)
                transforms_output_path = output_dir + 'transforms.json'
                with open(transforms_output_path, 'w') as f:
                    f.write(json.dumps(transforms))

            name = os.path.basename(path)
            if 'name' in raw_data_info and len(raw_data_info['name']) > 0:
                name = raw_data_info['name']

            result = {
                'file_path': output_dir,
                'frame_count': count,
                'name': name,
                'original_id': int(raw_data_info['original_id']),
                'candidates': raw_data_info['candidates'],
                'frames': frame_time
            }
            return result
        except Exception as e:
            print(e)
            raise(e)

    @staticmethod
    def __transform_to_dict(seq_num, transform):
        dict_translation = {"x": transform.translation.x, "y": transform.translation.y, "z": transform.translation.z}
        dict_rotation = {"x": transform.rotation.x, "y": transform.rotation.y, "z": transform.rotation.z, "w": transform.rotation.w}
        rotation_euler = tf.transformations.euler_from_quaternion((transform.rotation.x, transform.rotation.y, transform.rotation.z, transform.rotation.w))
        dict_rotation_euler = {"roll": rotation_euler[0], "pitch": rotation_euler[1], "yaw": rotation_euler[2]}
        dict_transform = {
            "seq_num": seq_num,
            "translation": dict_translation,
            "rotation": dict_rotation,
            "rotation_euler": dict_rotation_euler
        }
        return dict_transform

    @staticmethod
    def __get_candidates(automan_info, project_id, original_id, selected_topics):
        path = '/projects/' + str(project_id) + '/originals/' + str(original_id) + '/candidates/'
        res = AutomanClient.send_get(automan_info, path).json()
        candidates = []
        topics = []
        for c in res["records"]:
            analyzed_info = json.loads(c['analyzed_info'])
            if analyzed_info['topic_name'] in selected_topics.keys():
                candidate = {
                    'candidate_id': c["candidate_id"],
                    'msg_type': analyzed_info['msg_type'],
                    'topic_name': analyzed_info['topic_name']
                }
                candidates.append(candidate)
                topics.append(analyzed_info['topic_name'])
        return candidates, topics

    @staticmethod
    def __process_pcd(msg, file_path):
        pc = PointCloud.from_msg(msg)
        pc.save(file_path + '.pcd')

    @staticmethod
    def __process_image(msg, _type, file_path, camera_mat=None, dist_coeff=None):
        image = None
        if "Compressed" in _type:
            bridge = CvBridge()
            image = bridge.compressed_imgmsg_to_cv2(msg, "bgr8")
        else:
            bridge = CvBridge()
            image = bridge.imgmsg_to_cv2(msg, "bgr8").astype('f')

        if camera_mat and dist_coeff:
            image = cv2.undistort(image, camera_mat, dist_coeff, None, camera_mat)

        cv2.imwrite(file_path + ".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 100])

    @staticmethod
    def __parse_calib(calib_path):
        fs = cv2.FileStorage(calib_path, cv2.FILE_STORAGE_READ)
        camera_extrinsic_mat = fs.getNode("CameraExtrinsicMat").mat()
        camera_mat = fs.getNode("CameraMat").mat()
        dist_coeff = np.transpose(fs.getNode("DistCoeff").mat())
        return camera_extrinsic_mat, camera_mat, dist_coeff


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--storage_type', required=True)
    parser.add_argument('--storage_info', required=True)
    parser.add_argument('--automan_info', required=True)
    parser.add_argument('--raw_data_info', required=True)
    args = parser.parse_args()
    automan_info = json.loads(args.automan_info)
    print('automan_info: ' + args.automan_info)
    print('storage_info: ' + args.storage_info)

    storage_client = StorageClientFactory.create(
        args.storage_type,
        json.loads(args.storage_info)
    )
    storage_client.download()
    path = storage_client.get_input_path()
    output_dir = storage_client.get_output_dir()
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    res = RosbagExtractor.extract(
        automan_info, path, [], output_dir, json.loads(args.raw_data_info))
    if args.storage_type == 'AWS_S3':
        storage_client.upload(automan_info)
    res = AutomanClient.send_result(automan_info, res)
    print(res)

