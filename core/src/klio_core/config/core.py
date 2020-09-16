# Copyright 2019-2020 Spotify AB
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import logging

import attr

from klio_core.config import _io as io
from klio_core.config import _utils as utils

logger = logging.getLogger("klio")

WORKER_DISK_TYPE_URL = (
    "compute.googleapis.com/projects/{project}/regions/{region}/"
    "diskTypes/{disk_type}"
)


@utils.config_object(key_prefix=None, allow_unknown_keys=False)
class BaseKlioConfig(object):
    """Klio config object representation of klio-job.yaml.

    Args:
        config_dict (dict): dictionary representation of configuration
            as parsed from klio-job.yaml.
    """

    job_name = attr.attrib(type=str)

    job_config = attr.attrib(repr=False)
    pipeline_options = attr.attrib(repr=False, default={})

    version = attr.attrib(type=int, default=2, repr=False)

    def __config_post_init__(self, config_dict):
        self._raw = config_dict

        self.job_config = KlioJobConfig(
            self.job_config, job_name=self.job_name, version=self.version,
        )
        self.pipeline_options = KlioPipelineConfig(
            self.pipeline_options,
            job_name=self.job_name,
            version=self.version,
        )

    def __repr__(self):
        return "KlioConfig(job_name=%s)" % self.job_name

    def as_dict(self):
        job_config_dict = self.job_config.as_dict()
        pipeline_opts_dict = self.pipeline_options.as_dict()
        base_config_dict = attr.asdict(self)
        base_config_dict["job_config"] = job_config_dict
        base_config_dict["pipeline_options"] = pipeline_opts_dict
        return base_config_dict


class KlioConfig(BaseKlioConfig):
    pass


@attr.attrs
class KlioIOConfigContainer(object):
    inputs = attr.attrib()
    outputs = attr.attrib()


@utils.config_object(key_prefix="job_config", allow_unknown_keys=True)
class KlioJobConfig(object):
    """Job-specific config representing the "job_config" key of klio-job.yaml.

    "job_config" is both for any user-specific job configuration needed,
    as well as klio-related configuration (i.e. timeouts, metrics).

    Args:
        config_dict (dict): dictionary representation of configuration
            as parsed from klio-job.yaml.
    """

    ATTRIBS_TO_SKIP = ["version", "job_name"]
    USER_ATTRIBS = []

    # required attributes
    job_name = utils.field(type=str, repr=True)
    version = utils.field(type=int)

    # optional attributes
    allow_non_klio_messages = utils.field(type=bool, default=False)
    metrics = utils.field(default={})
    blocking = utils.field(type=bool, default=False)

    def __config_post_init__(self, config_dict):
        self._raw = config_dict
        self._scanned_io_subclasses = None

        self._parse_io(config_dict)

        declared_config = self._as_dict()
        for key, value in self._raw.items():
            if key not in declared_config:
                # set user attributes to job_config - but only the first
                # level, for example, from this
                # job_config:
                #    foo:
                #      key1: value1
                #      list1:
                #        - one
                #        - two
                # gets parsed to:
                # job_config.foo -> {"key1": "value1", "alist": ["one", "two"]}
                setattr(self, key, value)
                # key track of user-set attributes so that when as_dict()
                # is called, we re-add it to what _as_dict() returns
                self.USER_ATTRIBS.append({key: value})

    def _parse_io(self, config_dict):
        event_inputs = self._create_config_objects(
            config_dict.get("events", {}).get("inputs", []),
            io.KlioIOType.EVENT,
            io.KlioIODirection.INPUT,
        )
        event_outputs = self._create_config_objects(
            config_dict.get("events", {}).get("outputs", []),
            io.KlioIOType.EVENT,
            io.KlioIODirection.OUTPUT,
        )
        self.events = KlioIOConfigContainer(
            inputs=event_inputs, outputs=event_outputs
        )

        data_inputs = self._create_config_objects(
            config_dict.get("data", {}).get("inputs", []),
            io.KlioIOType.DATA,
            io.KlioIODirection.INPUT,
        )
        data_outputs = self._create_config_objects(
            config_dict.get("data", {}).get("outputs", []),
            io.KlioIOType.DATA,
            io.KlioIODirection.OUTPUT,
        )
        self.data = KlioIOConfigContainer(
            inputs=data_inputs, outputs=data_outputs
        )

    def _get_all_config_subclasses(self):
        if self._scanned_io_subclasses is not None:
            return self._scanned_io_subclasses

        # notice this will end up including intermediate classes but that
        # shouldn't matter since they shouldn't "support" any valid
        # combinations of type/direction
        all_subclasses = []

        def traverse(cls):
            for subclass in cls.__subclasses__():
                all_subclasses.append(subclass)
                traverse(subclass)

        traverse(io.KlioIOConfig)
        self._scanned_io_subclasses = all_subclasses
        return all_subclasses

    def _create_config_objects(self, configs, io_type, io_direction):
        options = dict(
            [
                (x.name, x)
                for x in self._get_all_config_subclasses()
                if x.supports_type(io_type)
                and x.supports_direction(io_direction)
            ]
        )
        objs = []
        for config in configs:
            type_name = config["type"].lower()
            if type_name not in options:
                raise Exception(
                    "{} is not a valid {} {}".format(
                        config["type"], io_type.name, io_direction.name
                    )
                )
            subclass = options[type_name]
            objs.append(subclass.from_dict(config, io_type, io_direction))
        return objs

    def _as_dict(self):
        config_dict = attr.asdict(
            self, filter=lambda x, _: x.name not in self.ATTRIBS_TO_SKIP
        )
        config_dict["events"] = {}
        config_dict["events"]["inputs"] = [
            ei.as_dict() for ei in self.events.inputs
        ]
        config_dict["events"]["outputs"] = [
            eo.as_dict() for eo in self.events.outputs
        ]

        config_dict["data"] = {}
        config_dict["data"]["inputs"] = [
            di.as_dict() for di in self.data.inputs
        ]
        config_dict["data"]["outputs"] = [
            do.as_dict() for do in self.data.outputs
        ]
        return config_dict

    def as_dict(self):
        config_dict = self._as_dict()
        for attrib in self.USER_ATTRIBS:
            for key, value in attrib.items():
                config_dict[key] = value

        return config_dict

    def __repr__(self):
        return "KlioJobConfig(job_name=%s)" % self.job_name


@utils.config_object(key_prefix="pipeline_options", allow_unknown_keys=True)
class KlioPipelineConfig(object):
    """Pipeline-specific config representing the "pipeline_options" key
    of klio-job.yaml.

    "pipeline_options" map 1:1 to options supported in Apache Beam and
    its runners (i.e. Dataflow). See https://github.com/apache/beam/blob/
    master/sdks/python/apache_beam/options/pipeline_options.py for
    available options.

    Any instance attribute not defined below but is available in Apache
    Beam or its runners will still be passed through when running the
    pipeline.

    Args:
        config_dict (dict): dictionary representation of configuration
            as parsed from klio-job.yaml.
    """

    ATTRIBS_TO_SKIP = ["version"]
    USER_ATTRIBS = []

    job_name = utils.field(repr=True, type=str)
    version = utils.field(type=int)

    runner = utils.field(type=str, default="DataflowRunner")
    streaming = utils.field(type=bool, default=True)

    # debug options
    experiments = utils.field(default=["beam_fn_api"])

    # setup options
    sdk_location = utils.field(type=str, default=None)
    setup_file = utils.field(type=str, default=None)
    requirements_file = utils.field(type=str, default=None)

    # GCP options
    project = utils.field(type=str, default=None)
    staging_location = utils.field(type=str, default=None)
    temp_location = utils.field(type=str, default=None)
    region = utils.field(type=str, default="europe-west1")
    subnetwork = utils.field(type=str, default=None)
    update = utils.field(type=bool, default=False)
    dataflow_endpoint = utils.field(type=str, default=None)
    service_account_email = utils.field(type=str, default=None)
    no_auth = utils.field(type=bool, default=False)
    template_location = utils.field(type=str, default=None)
    labels = utils.field(default=[])
    label = utils.field(type=str, default=None)
    transform_name_mapping = utils.field(type=str, default=None)
    enable_streaming_engine = utils.field(type=bool, default=False)
    dataflow_kms_key = utils.field(type=str, default=None)
    flexrs_goal = utils.field(
        type=str,
        default=None,
        validator=attr.validators.optional(
            attr.validators.in_(["COST_OPTIMIZED", "SPEED_OPTIMIZED"])
        ),
    )

    # worker options
    autoscaling_algorithm = utils.field(
        type=str,
        default="NONE",
        validator=attr.validators.optional(
            attr.validators.in_(["THROUGHPUT_BASED", "NONE"])
        ),
    )
    num_workers = utils.field(type=int, default=2)
    disk_size_gb = utils.field(type=int, default=32)
    worker_machine_type = utils.field(type=str, default="n1-standard-2")
    worker_harness_container_image = utils.field(type=str, default=None)
    worker_disk_type = utils.field(
        type=str,
        default=None,
        validator=attr.validators.optional(
            attr.validators.in_(["local-ssd", "pd-ssd", "pd-standard"])
        ),
    )
    use_public_ips = utils.field(type=bool, default=None)
    min_cpu_platform = utils.field(type=str, default=None)
    dataflow_worker_jar = utils.field(type=str, default=None)

    # profiling options
    profile_location = utils.field(type=str, default=None)
    profile_cpu = utils.field(type=bool, default=None)
    profile_memory = utils.field(type=bool, default=None)
    profile_sample_rate = utils.field(type=float, default=None)

    def __config_post_init__(self, config_dict):
        if self.label:
            self.labels.append(self.label)

        self.max_num_workers = max(2, self.num_workers)

        if self.worker_disk_type is not None:
            self.worker_disk_type = WORKER_DISK_TYPE_URL.format(
                project=self.project,
                region=self.region,
                disk_type=self.worker_disk_type,
            )

        declared_config = self._as_dict()
        for key, value in config_dict.items():
            if key not in declared_config:
                # set user attributes to job_config - but only the first
                # level, for example, from this
                # pipeline_options:
                #    foo:
                #      key1: value1
                #      list1:
                #        - one
                #        - two
                # gets parsed to:
                # pipeline_options.foo ->
                #   {"key1": "value1", "alist": ["one", "two"]}
                setattr(self, key, value)
                # key track of user-set attributes so that when as_dict()
                # is called, we re-add it to what _as_dict() returns
                self.USER_ATTRIBS.append({key: value})

    def _as_dict(self):
        return attr.asdict(
            self, filter=lambda x, _: x.name not in self.ATTRIBS_TO_SKIP
        )

    def as_dict(self):
        config_dict = self._as_dict()
        for attrib in self.USER_ATTRIBS:
            for key, value in attrib.items():
                config_dict[key] = value

        return config_dict

    def __repr__(self):
        return "KlioPipelineConfig(job_name=%s)" % self.job_name
