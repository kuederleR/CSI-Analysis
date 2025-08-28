from setuptools import find_packages, setup
import os
from glob import glob
package_name = 'csi_ros'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (
            os.path.join("share", package_name, "launch"),
            glob(os.path.join("launch", "*launch.[pxy][yma]*")),
        ),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ryan',
    maintainer_email='ryan@rkuederle.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            "csi_pub = csi_ros.csi_pub:main",
            "static_base_to_wifi_tf = csi_ros.static_base_to_wifi_tf:main",
            "world_to_base_tf = csi_ros.world_to_base_tf:main",
            "world_to_home_tf = csi_ros.world_to_home_tf:main",
        ],
    },
)
