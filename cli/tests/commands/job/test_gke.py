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

import glom
import pytest

from kubernetes import client

from klio_core import config

from klio_cli import cli
from klio_cli.commands.job import gke as job_gke


@pytest.fixture
def mock_os_environ(mocker):
<<<<<<< HEAD
    return mocker.patch.dict(
        job_gke.base.os.environ, {"USER": "cookiemonster"}
    )
=======
    return mocker.patch.dict(job_gke.base.os.environ, {"USER": "cookiemonster"})
>>>>>>> 8c5989b... [cli][core] Fix GKE ref, fix update command error, fix klio job stop restarting pods


@pytest.fixture
def klio_config():
    conf = {
        "job_name": "test-job",
        "version": 1,
        "pipeline_options": {
            "worker_harness_container_image": "test-image",
            "region": "some-region",
            "project": "test-project",
        },
        "job_config": {
            "inputs": [
                {
                    "topic": "foo-topic",
                    "subscription": "foo-sub",
                    "data_location": "foo-input-location",
                }
            ],
            "outputs": [
                {
                    "topic": "foo-topic-output",
                    "data_location": "foo-output-location",
                }
            ],
        },
    }
    return config.KlioConfig(conf)


@pytest.fixture
def docker_runtime_config():
    return cli.DockerRuntimeConfig(
        image_tag="foo-123",
        force_build=False,
        config_file_override="klio-job2.yaml",
    )


@pytest.fixture
def run_job_config():
    return cli.RunJobConfig(direct_runner=False, update=False, git_sha="12345678")


@pytest.fixture
def mock_docker_client(mocker):
    mock_client = mocker.Mock()
    mock_container = mocker.Mock()
    mock_container.wait.return_value = {"StatusCode": 0}
    mock_container.logs.return_value = [b"a log line\n", b"another log line\n"]
    mock_client.containers.run.return_value = mock_container
    return mock_client


@pytest.fixture
def run_pipeline_gke(
    klio_config,
    docker_runtime_config,
    run_job_config,
    mock_docker_client,
    mock_os_environ,
    monkeypatch,
):
    job_dir = "/test/dir/jobs/test_run_job"
    pipeline = job_gke.RunPipelineGKE(
        job_dir=job_dir,
        klio_config=klio_config,
        docker_runtime_config=docker_runtime_config,
        run_job_config=run_job_config,
    )

    monkeypatch.setattr(pipeline, "_docker_client", mock_docker_client)
    return pipeline


@pytest.fixture
def deployment_config():
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": "gke-baseline-random-music",
            "namespace": "sigint",
            "labels": {"app": "gke-baseline-random-music"},
        },
        "spec": {
            "replicas": 100,
            "strategy": {"type": "Recreate"},
            "selector": {
                "matchLabels": {
                    "app": "gke-baseline-random-music",
                    "role": "gkebaselinerandommusic",
                }
            },
            "template": {
                "metadata": {
                    "labels": {
                        "app": "gke-baseline-random-music",
                        "role": "gkebaselinerandommusic",
                    },
                    "annotations": {
                        "podpreset.admission.spotify.com/exclude": (
                            "container/" "ffwd-java-shim, environment/ffwd"
                        )
                    },
                },
                "spec": {
                    "volumes": [
                        {
                            "name": "google-cloud-key",
                            "secret": {"secretName": "lynn-podcast-key"},
                        }
                    ],
                    "containers": [
                        {
                            "name": "gke-baseline-random-music",
                            "image": ("gcr.io/sigint/gke-base" "line-random-music-gke"),
                            "resources": {
                                "requests": {"cpu": 4, "memory": "16G"},
                                "limits": {"cpu": 8, "memory": "20G"},
                            },
                            "volumeMounts": [
                                {
                                    "name": "google-cloud-key",
                                    "mountPath": "/var/secrets/google",
                                }
                            ],
                            "env": [
                                {
                                    "name": "GOOGLE_APPLICATION_CREDENTIALS",
                                    "value": "/var/secrets/google/key.json",
                                }
                            ],
                        }
                    ],
                },
            },
        },
    }


@pytest.fixture
def deployment_resp():
    # TODO: We can grab these from deployment_config

    container = client.V1Container(
        name="gke-baseline-random-music",
        image="gcr.io/sigint/gke-baseline-random-music-gke",
        ports=[client.V1ContainerPort(container_port=80)],
        resources=client.V1ResourceRequirements(
            requests={"cpu": 4, "memory": "16G"},
            limits={"cpu": 8, "memory": "20G"},
        ),
    )

    # Create and configurate a spec section
    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(
            labels={
                "app": "gke-baseline-random-music",
                "role": "gkebaselinerandommusic",
            },
            annotations={
                "podpreset.admission.spotify.com/exclude": (
                    "container/" "ffwd-java-shim, environment/ffwd"
                )
            },
        ),
        spec=client.V1PodSpec(containers=[container]),
    )

    # Create the specification of deployment
    spec = client.V1DeploymentSpec(
        replicas=100,
        template=template,
        selector={
            "matchLabels": {
                "app": "gke-baseline-random-music",
                "role": "gkebaselinerandommusic",
            }
        },
    )

    # Instantiate the deployment object
    deployment = client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(name="gke-baseline-random-music"),
        spec=spec,
    )

    return deployment


@pytest.fixture
def deployment_response_list(deployment_config, deployment_resp):
    resp = client.models.v1_deployment_list.V1DeploymentList(items=[deployment_resp])
    return resp


@pytest.fixture
def deployment_response_list_not_exist():
    resp = client.models.v1_deployment_list.V1DeploymentList(items=[])
    return resp


def test_update_deployment(
    deployment_config, run_pipeline_gke, deployment_resp, monkeypatch, mocker
):
    deployment_name = deployment_config["metadata"]["name"]
    namespace = deployment_config["metadata"]["namespace"]
    mock_k8s_client = mocker.Mock()
    mock_k8s_client.patch_namespaced_deployment.return_value = deployment_resp

    # run_pipeline_gke = job_gke.RunPipelineGKE("/some/job/dir")

<<<<<<< HEAD
    monkeypatch.setattr(
        run_pipeline_gke, "_kubernetes_client", mock_k8s_client
    )
    monkeypatch.setattr(
        run_pipeline_gke, "_deployment_config", deployment_config
    )
=======
    monkeypatch.setattr(run_pipeline_gke, "_kubernetes_client", mock_k8s_client)
    monkeypatch.setattr(run_pipeline_gke, "_deployment_config", deployment_config)
>>>>>>> 8c5989b... [cli][core] Fix GKE ref, fix update command error, fix klio job stop restarting pods
    run_pipeline_gke._update_deployment()
    mock_k8s_client.patch_namespaced_deployment.assert_called_once_with(
        name=deployment_name,
        namespace=namespace,
        body=deployment_config,
    )


# Tests for internal functions
@pytest.mark.parametrize(
    "deployed,is_exists",
    (
        (["deployment-1", "gke-baseline-random-music"], True),
        (["deployment-2"], False),
    ),
)
def test_deployment_exists(
    deployment_resp,
    deployment_config,
    run_pipeline_gke,
    deployment_response_list,
    monkeypatch,
    mocker,
    deployed,
    is_exists,
):
    mock_k8s_client = mocker.Mock()
    mock_k8s_client.patch_namespaced_deployment.return_value = deployment_resp
    mock_k8s_client.list_namespaced_deployment.return_value = deployment_response_list
    monkeypatch.setattr(run_pipeline_gke, "_kubernetes_client", mock_k8s_client)
    monkeypatch.setattr(run_pipeline_gke, "_deployment_config", deployment_config)
    run_pipeline_gke._deployment_exists()
    mock_k8s_client.list_namespaced_deployment.assert_called_once_with(
        namespace=deployment_config["metadata"]["namespace"]
    )


# Tests for user facing functions
@pytest.mark.parametrize(
    "deployment_exists,update_flag",
    (
        (True, False),
        (False, True),
        # TODO: Add False, False and confirm warning log
    ),
)
def test_apply_deployment(
    monkeypatch,
    mocker,
    run_pipeline_gke,
    run_job_config,
    docker_runtime_config,
    deployment_config,
    deployment_resp,
    deployment_response_list,
    deployment_response_list_not_exist,
    deployment_exists,
    update_flag,
):
    # New Deployment
    run_job_config = run_job_config._replace(update=update_flag)
    monkeypatch.setattr(run_pipeline_gke, "run_job_config", run_job_config)
    mock_k8s_client = mocker.Mock()
    mock_k8s_client.create_namespaced_deployment.return_value = deployment_resp
    mock_k8s_client.patch_namespaced_deployment.return_value = deployment_resp
    mock_k8s_client.list_namespaced_deployment.return_value = (
        deployment_response_list
        if deployment_exists
        else deployment_response_list_not_exist
    )
    monkeypatch.setattr(run_pipeline_gke, "_kubernetes_client", mock_k8s_client)
    monkeypatch.setattr(run_pipeline_gke, "_deployment_config", deployment_config)
    deployment_name = deployment_config["metadata"]["name"]
    namespace = deployment_config["metadata"]["namespace"]
    image_path = "spec.template.spec.containers.0.image"
    image_base = glom.glom(deployment_config, image_path)
    full_image = f"{image_base}:{docker_runtime_config.image_tag}"
    run_pipeline_gke._apply_image_to_deployment_config()
    run_pipeline_gke._apply_deployment()
    assert glom.glom(run_pipeline_gke._deployment_config, image_path) == full_image
    glom.assign(deployment_config, image_path, full_image)
    if deployment_exists:
        if update_flag:
            mock_k8s_client.patch_namespaced_deployment.assert_called_once_with(
                name=deployment_name,
                namespace=namespace,
                body=deployment_config,
            )
    else:
        mock_k8s_client.create_namespaced_deployment.assert_called_once_with(
            body=deployment_config, namespace=namespace
        )


def test_delete(
    monkeypatch,
    mocker,
    deployment_response_list,
    deployment_config,
):
    namespace = deployment_config["metadata"]["namespace"]
    deployment_name = deployment_config["metadata"]["name"]
    mock_k8s_client = mocker.Mock()
    mock_k8s_client.patch_namespaced_deployment.return_value = deployment_resp
    mock_k8s_client.list_namespaced_deployment.return_value = deployment_response_list

    delete_pipeline_gke = job_gke.DeletePipelineGKE("/some/job/dir")

    monkeypatch.setattr(delete_pipeline_gke, "_kubernetes_client", mock_k8s_client)
    monkeypatch.setattr(delete_pipeline_gke, "_deployment_config", deployment_config)
    delete_pipeline_gke.delete()
    mock_k8s_client.delete_namespaced_deployment.assert_called_once_with(
        name=deployment_name,
        namespace=namespace,
        body=client.V1DeleteOptions(
            propagation_policy="Foreground", grace_period_seconds=5
        ),
    )


def test_stop(deployment_resp, deployment_config, monkeypatch, mocker):
    deployment_name = deployment_config["metadata"]["name"]
    namespace = deployment_config["metadata"]["namespace"]
    mock_k8s_client = mocker.Mock()
    mock_k8s_client.patch_namespaced_deployment.return_value = deployment_resp

    stop_pipeline_gke = job_gke.StopPipelineGKE("/some/job/dir")

    monkeypatch.setattr(stop_pipeline_gke, "_kubernetes_client", mock_k8s_client)
    monkeypatch.setattr(stop_pipeline_gke, "_deployment_config", deployment_config)
    stop_pipeline_gke.stop()
    mock_k8s_client.patch_namespaced_deployment.assert_called_once_with(
        name=deployment_name, namespace=namespace, body=deployment_config,
    )
