import zenoh
from zenoh import QueryTarget
import logging
import warnings
import atexit
import json
import time
import keelson
from terminal_inputs import terminal_inputs
from keelson.payloads.ImuReading_pb2 import ImuReading
from keelson.payloads.PointCloud_pb2 import PointCloud
from keelson.payloads.PackedElementField_pb2 import PackedElementField
from keelson.payloads.CompressedImage_pb2 import CompressedImage

session = None
args = None
pub_camera_panorama = None


def query_process(query):
    """
    Query from a service

    Args:
        query (zenoh.Query): Zenoh query object
    Returns:
        envelope (bytes) with compressed image payload
    """

    ingress_timestamp = time.time_ns()
    
    query_key = query.selector
    logging.debug(f">> [Query] Received query key {query_key}")

    query_payload = query.value.payload
    logging.debug(f">> [Query] Received query payload {query_payload}")

    # Expecting not a payload 

    # Triggering get requests for camera images

    # Camera image getter

    replies = session.get(
        args.point_cloud_query,
        zenoh.Queue(),
        target=QueryTarget.BEST_MATCHING(),
        consolidation=zenoh.QueryConsolidation.NONE(),
    )

    arr_point_clouds = []

    for reply in replies.receiver:

        try:
            print(
                ">> Received ('{}': '{}')".format(reply.ok.key_expr, reply.ok.payload)
            )
            # Unpacking image    
            received_at, enclosed_at, content = keelson.uncover(reply.ok.payload)
            logging.debug(f"content {content} received_at: {received_at}, enclosed_at {enclosed_at}")

            point_cloud = PointCloud.FromString(content)

            point_cloud_object = {
                "timestamp": point_cloud.timestamp.ToDatetime(),
                "frame_id": point_cloud.frame_id,
                "pose": point_cloud.pose,
                "point_stride ": point_cloud.point_stride,
                "fields": point_cloud.fields,
                "data": point_cloud.data
            }

            arr_point_clouds.append(point_cloud_object)

        except:
            print(">> Received (ERROR: '{}')".format(reply.err.payload))


  
    ##########################
    # TODO: Do something HERE and return something
    ##########################


    # Packing panorama created
    newImage = CompressedImage()
    newImage.timestamp.FromNanoseconds(ingress_timestamp)
    newImage.frame_id = "foxglove_frame_id"
    newImage.data = b"binary_image_data" # Binary image data 
    newImage.format = "jpeg" # supported formats `webp`, `jpeg`, `png`
    serialized_payload = newImage.SerializeToString()
    envelope = keelson.enclose(serialized_payload)

    # Replaying on the query with the panorama image in an keelson envelope
    query.reply(zenoh.Sample(str(query.selector), envelope))
    # query.reply(zenoh.Sample(str(query.selector), "OK")) # Simple response for testing




def subscriber_camera_publisher(data):
    """
    Subscriber trigger by camera image incoming
    """

    ingress_timestamp = time.time_ns()
    
    data_key = data.selector
    logging.debug(f">> [Query] Received query key {data_key}")

    data_payload = data.value.payload
    logging.debug(f">> [Query] Received query payload {data_payload}")

    received_at, enclosed_at, content = keelson.uncover(data_payload)
    logging.debug(f"content {content} received_at: {received_at}, enclosed_at {enclosed_at}")
    point_cloud = PointCloud.FromString(content)

    point_cloud_object = {
            "timestamp": point_cloud.timestamp.ToDatetime(),
            "frame_id": point_cloud.frame_id,
            "pose": point_cloud.pose,
            "point_stride ": point_cloud.point_stride,
            "fields": point_cloud.fields,
            "data": point_cloud.data
        }


    ##########################
    # TODO: Do something HERE and return something
    ##########################


    # Packing panorama created
    newImage = CompressedImage()
    newImage.timestamp.FromNanoseconds(ingress_timestamp)
    newImage.frame_id = "foxglove_frame_id"
    newImage.data = b"binary_image_data" # Binary image data 
    newImage.format = "jpeg" # supported formats `webp`, `jpeg`, `png`
    serialized_payload = newImage.SerializeToString()
    envelope = keelson.enclose(serialized_payload)
    pub_camera_panorama.put(envelope)


def fixed_hz_publisher():

    ingress_timestamp = time.time_ns()

    # Camera image getter
    replies = session.get(
        args.camera_query,
        zenoh.Queue(),
        target=QueryTarget.BEST_MATCHING(),
        consolidation=zenoh.QueryConsolidation.NONE(),
    )


    for reply in replies.receiver:
        try:
            print(
                ">> Received ('{}': '{}')".format(reply.ok.key_expr, reply.ok.payload)
            )
            # Unpacking image    
            received_at, enclosed_at, content = keelson.uncover(reply.ok.payload)
            logging.debug(f"content {content} received_at: {received_at}, enclosed_at {enclosed_at}")
            Image = CompressedImage.FromString(content)

            img_dic = {
                "timestamp": Image.timestamp.ToDatetime(),
                "frame_id": Image.frame_id,
                "data": Image.data,
                "format": Image.format
            }

        except:
            print(">> Received (ERROR: '{}')".format(reply.err.payload))

    ##########################
    # TODO: STITCHING HERE
    ##########################


    # Packing panorama created
    newImage = CompressedImage()
    newImage.timestamp.FromNanoseconds(ingress_timestamp)
    newImage.frame_id = "foxglove_frame_id"
    newImage.data = b"binary_image_data" # Binary image data 
    newImage.format = "jpeg" # supported formats `webp`, `jpeg`, `png`
    serialized_payload = newImage.SerializeToString()
    envelope = keelson.enclose(serialized_payload)
    pub_camera_panorama.put(envelope)
    time.sleep(1 / args.fixed_hz)



"""
#####################################################
# Keelson Processor 
"""
if __name__ == "__main__":
    # Input arguments and configurations
    args = terminal_inputs()
    # Setup logger
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s", level=args.log_level
    )
    logging.captureWarnings(True)
    warnings.filterwarnings("once")

    ## Construct session
    logging.info("Opening Zenoh session...")
    conf = zenoh.Config()
    if args.connect is not None:
        conf.insert_json5(zenoh.config.CONNECT_KEY, json.dumps(args.connect))
    session = zenoh.open(conf)

    def _on_exit():
        session.close()

    atexit.register(_on_exit)
    logging.info(f"Zenoh session established: {session.info()}")

    #################################################
    # Setting up PUBLISHER

    # Result publisher 
    key_exp_pub_camera_pano = keelson.construct_pub_sub_key(
        realm=args.realm,
        entity_id=args.entity_id,
        subject="compressed_image",  # Needs to be a supported subject
        source_id="panorama/" + args.output_id,
    )
    pub_camera_panorama = session.declare_publisher(
        key_exp_pub_camera_pano,
        priority=zenoh.Priority.INTERACTIVE_HIGH(),
        congestion_control=zenoh.CongestionControl.DROP(),
    )
    logging.info(f"Created publisher: {key_exp_pub_camera_pano}")


    #################################################
    # Setting up Querible

    # Camera panorama
    key_exp_query = keelson.construct_req_rep_key(
        realm=args.realm,
        entity_id=args.entity_id,
        responder_id="panorama",
        procedure="do_some_tracking",
    )
    query_camera_panorama = session.declare_queryable(
        key_exp_query,
        query_process
    )
    logging.info(f"Created queryable: {key_exp_query}")

    #################################################

    try:

        # TODO: SUBSCRIPTION initialization 
        if args.trigger_sub is not None:
            logging.info(f"Trigger Subscribing Key: {args.trigger_sub}")
            key_exp_sub_camera = keelson.construct_pub_sub_key(
                realm=args.realm,
                entity_id=args.entity_id,
                subject="compressed_image",  # Needs to be a supported subject
                source_id=args.trigger_sub,
            )

            # Declaring zenoh publisher
            sub_camera = session.declare_subscriber(
                key_exp_sub_camera, subscriber_camera_publisher
            )

        # TODO: FIXED HZ initialization 
        if args.trigger_hz is not None:
            logging.info(f"Trigger Hz: {args.trigger_hz}")
            while True:
                fixed_hz_publisher()

    except KeyboardInterrupt:
        logging.info("Program ended due to user request (Ctrl-C)")
    except Exception as e:
        logging.error(f"Program ended due to error: {e}")

    # finally:
    #     logging.info("Closing Zenoh session...")
    #     session.close()
    #     logging.info("Zenoh session closed.")
